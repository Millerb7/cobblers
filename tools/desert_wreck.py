#!/usr/bin/env python
"""The Brass Petrel on the southern desert beach, from data/desert_wreck.json: a barque the Great Tide drove into the
dune wall, her bow buried to the rail and her stern on the flats; the dead reef bleached in front of her; Castellan,
the sandcastle at the tide line; and the strand's own Habitat pool.

The owner, 2026-10-05: "The southern desert beach is the last empty stretch I can name. Build a wreck half-buried in
the dunes -- something the water left behind, with an interior worth entering ... A desert meeting a sea should feel
like neither." Every part is an existing, proven piece; nothing here is new machinery:

  the wreck     vanilla 1.21.1 blocks, seated the repository's way (tools/dune_ruin.py's): the deck D is
                max(ground under the transom row) + wreck.stern_show, ground from tools/ground.py (the canonical
                heightmap, rounded), never a world. The keel is D - wreck.depth. Every hull cell is written, solid or
                air, including the parts under the dune; the dune's own sand lies on the deck where the ground is over
                it, never written. The hold's sand spill IS written (the ground's material 4-10 under the surface is
                not known). Rooms: the cargo hold, the crew's berth under the cabin, the master's cabin over it.
  the reef      dead coral blocks, bone and calcite in heads over the flats in front of the stern, from a fixed hash.
  Castellan     NOT blocks: a Palossand kept by tools/resident_encounters.py's keeper (resident_files(), called, as
                tools/far_south.py does), dormant until a player comes within its trigger. Gated (appears_after), so
                no re-application step summons it. The pack writes only its flag.
  the pool      NOT in this pack: two natural Habitat Blocks and a Habitat pool, records this tool writes into
                data/habitat_blocks.json and data/spawns.json (`records --write`), placed by tools/habitat_blocks.py
                (R9E) and compiled by tools/compile_spawns.py.
  the find      NOT in this pack: an ADR-002 cache in data/rewards.json (`records --write`), its trigger box round
                the sea chest (a barrel) this pack writes.

  python tools/desert_wreck.py build   [--source-root R] [--out DIR]   write the pack
  python tools/desert_wreck.py report  [--source-root R]               the numbers, bounds and steps; writes nothing
  python tools/desert_wreck.py records [--write] [--source-root R]     the Habitat Blocks, pool and cache records
                                                                      (--write replaces this place's records in the
                                                                      three data files)

The re-application (tools/reapply.py, NOT edited here; the integrator wires it): placement_steps() is R9DW, put before
R9E with the other block passes. No entity step: the one resident is gated.
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
import function_limits  # noqa: E402

DATA = ROOT / "data" / "desert_wreck.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_desert_wreck"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
REWARDS = ROOT / "data" / "rewards.json"
SCHEMA = "cobblers.desert-wreck/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
SEA = 62              # data/world.json sea level: a column whose ground is under it is water (tools/water_mask.py)
TUMBLE = (0, 0, 0, 0, 1, 1, 2, 3)   # how far the hull's half-width narrows k rows under the deck (k = 0 .. depth)
CLEAR_MARGIN = 3
CLEAR_OVER = 4
# never a light source other than a lantern, never a bubble-column block, never water (data/desert_wreck.json blocks)
FORBIDDEN = {"minecraft:light", "minecraft:glowstone", "minecraft:sea_lantern", "minecraft:shroomlight",
             "minecraft:torch", "minecraft:wall_torch", "minecraft:soul_torch", "minecraft:candle",
             "minecraft:soul_sand", "minecraft:magma_block", "minecraft:water", "minecraft:bubble_column",
             "minecraft:chest", "minecraft:red_bed", "minecraft:jack_o_lantern", "minecraft:redstone_lamp"}
# the plants a beach or dune grows: the clearing removes only these, NEVER #minecraft:replaceable (it holds water)
PLANTS = ("minecraft:dead_bush", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern",
          "minecraft:large_fern", "minecraft:cactus", "minecraft:sugar_cane", "#minecraft:logs", "#minecraft:leaves")
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class WreckError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise WreckError("%s: schema must be %s" % (path, SCHEMA))
    w = doc["wreck"]
    if w["depth"] != len(TUMBLE) - 1:
        raise WreckError("wreck.depth must be %d: the hull's narrowing (TUMBLE) is written for it" % (len(TUMBLE) - 1))
    if w["hold"]["floor_below_deck"] != w["depth"] - 1:
        raise WreckError("the hold floor lies one over the keel: floor_below_deck = depth - 1")
    if len(w["bow_taper"]) + len(w["stern_taper"]) >= w["length"]:
        raise WreckError("the bow and stern tapers overlap")
    if not (w["hold"]["spill_full_to"] < w["hold"]["spill_slope_to"] < w["bulkhead"] < w["cabin"]["from"] < w["length"] - 1):
        raise WreckError("spill, bulkhead and cabin must follow one another from the bow")
    ids = set(doc["blocks"]["ids"])
    bad = sorted(ids & FORBIDDEN)
    if bad:
        raise WreckError("blocks.ids carries forbidden blocks: %s" % bad)
    for r in doc["residents"]:
        pk = r["pokemon"]
        if not (0 < pk["trigger"] < pk["leash"]):
            raise WreckError("%s: the trigger must be inside the leash" % pk["id"])
    pb = doc["pool"]["blocks"]
    if len({b["id"] for b in pb}) != len(pb):
        raise WreckError("pool block ids must be unique")
    return doc


def base(state):
    return state.split("[")[0].split("{")[0]


def _h(x, z, salt=0):
    """A fixed hash of a column: the same on every rebuild."""
    v = (x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)
    v = (v ^ (v >> 13)) * 1274126177
    return (v ^ (v >> 16)) & 0x7FFFFFFF


def _pick(palette, x, z, salt):
    total = sum(w for _s, w in palette)
    r = _h(x, z, salt) % total
    for s, w in palette:
        if r < w:
            return s
        r -= w
    return palette[-1][0]


def noise(x, z, grid, salt=11):
    """Value noise in [0, 1): the fixed hash on a `grid`-block lattice, smoothly interpolated. The same every rebuild."""
    gx, gz = x // grid, z // grid
    fx, fz = (x % grid) / grid, (z % grid) / grid
    sx, sz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    c = [[(_h(gx + i, gz + j, salt) % 1000) / 1000.0 for j in (0, 1)] for i in (0, 1)]
    a = c[0][0] + (c[1][0] - c[0][0]) * sx
    b = c[0][1] + (c[1][1] - c[0][1]) * sx
    return a + (b - a) * sz


def _text(lines):
    return ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])


def wall_sign(facing, lines):
    return "minecraft:spruce_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:[%s]}}" % (facing, _text(lines))


def fence(n=False, s=False, e=False, w=False):
    b = lambda v: "true" if v else "false"  # noqa: E731
    return "minecraft:spruce_fence[east=%s,north=%s,south=%s,waterlogged=false,west=%s]" % (b(e), b(n), b(s), b(w))


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """Two passes of blocks, {(x, y, z): state}: the structure, then what hangs on it or stands on it (a sign, a
    ladder, a trapdoor, a lantern, a carpet, a banner), so nothing attached is placed before what holds it up."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        w = self.w = doc["wreck"]
        self.W, self.Z0, self.L = w["x"], w["bow_z"], w["length"]
        self.allowed = set(doc["blocks"]["ids"])
        self.solid, self.hung = {}, {}
        transom = [(self.W + lx, self.Z0 + self.L - 1) for lx in range(-self.hw0(self.L - 1), self.hw0(self.L - 1) + 1)]
        self.D = max(g(x, z) for x, z in transom) + w["stern_show"]
        self.K = self.D - w["depth"]
        self.floor = self.D - w["hold"]["floor_below_deck"]

    # the hull's shape
    def hw0(self, lz):
        w = self.w
        bt, st = w["bow_taper"], w["stern_taper"]
        if lz < len(bt):
            return bt[lz]
        if lz >= self.L - len(st):
            return st[lz - (self.L - len(st))]
        return w["half_beam"]

    def hw(self, lz, y):
        if not (0 <= lz < self.L and self.K <= y <= self.D):
            return -1
        return self.hw0(lz) - TUMBLE[self.D - y]

    def inside(self, lx, lz, y):
        return abs(lx) <= self.hw(lz, y)

    def shell(self, lx, lz, y):
        return self.inside(lx, lz, y) and (
            y == self.K or lz in (0, self.L - 1) or abs(lx) == self.hw(lz, y)
            or not self.inside(lx, lz, y - 1) or not self.inside(lx, lz - 1, y) or not self.inside(lx, lz + 1, y))

    def xz(self, lx, lz):
        return self.W + lx, self.Z0 + lz

    def ground(self, lx, lz):
        return self.g(*self.xz(lx, lz))

    # writing
    def _put(self, into, x, y, z, state):
        if base(state) not in self.allowed:
            raise WreckError("%s is not in data/desert_wreck.json blocks.ids" % base(state))
        into[(x, y, z)] = state

    def put(self, lx, y, lz, state):
        x, z = self.xz(lx, lz)
        self.hung.pop((x, y, z), None)
        self._put(self.solid, x, y, z, state)

    def hang(self, lx, y, lz, state):
        x, z = self.xz(lx, lz)
        self.solid.pop((x, y, z), None)
        self._put(self.hung, x, y, z, state)

    def put_at(self, x, y, z, state):
        self._put(self.solid, x, y, z, state)

    def hang_at(self, x, y, z, state):
        self._put(self.hung, x, y, z, state)

    def blocks(self):
        out = dict(self.solid)
        out.update(self.hung)
        return out


def hull(p):
    """Every cell of the hull from the keel to the deck: the shell (tarred low, spruce high, a wale), the hold floor,
    the deck, the hold's air; the beams under the deck."""
    b = p.doc["blocks"]
    D, K, F = p.D, p.K, p.floor
    for lz in range(p.L):
        for y in range(K, D + 1):
            h = p.hw(lz, y)
            for lx in range(-h, h + 1):
                if p.shell(lx, lz, y):
                    straight = p.hw0(lz) == p.w["half_beam"] and abs(lx) == h and 0 < lz < p.L - 1
                    if y == D - 1 and straight:
                        st = "%s[axis=z]" % b["wale"]
                    else:
                        st = b["hull_low"] if y <= D - 3 else b["hull_high"]
                elif y == D:
                    st = b["deck"]
                elif y == F:
                    st = b["floor"]
                else:
                    st = "minecraft:air"
                p.put(lx, y, lz, st)
    # deck beams under the deck, across the hold, every beams_every blocks aft of the spill
    for lz in range(p.w["hold"]["spill_slope_to"] + 1, p.L - 1):
        if lz % p.w["beams_every"]:
            continue
        h = p.hw(lz, D - 1)
        for lx in range(-h + 1, h):
            p.put(lx, D - 1, lz, "%s[axis=x]" % b["beam"])


def spill(p):
    """The sand that came in through the stove-in bow: the hold full to the deck at the bow, sloping to the floor."""
    hold = p.w["hold"]
    D, F = p.D, p.floor
    for lz in range(1, hold["spill_slope_to"] + 1):
        top = D - 1 if lz <= hold["spill_full_to"] else D - 1 - (lz - hold["spill_full_to"])
        for y in range(F + 1, top + 1):
            h = p.hw(lz, y)
            for lx in range(-h + 1, h):
                if not p.shell(lx, lz, y):
                    p.put(lx, y, lz, "minecraft:sand")


def bulkhead_and_breach(p):
    """The bulkhead between the cargo hold and the berth (a doorway in it), and the stove-in transom: the way in."""
    b = p.doc["blocks"]
    D, F = p.D, p.floor
    bz = p.w["bulkhead"]
    for y in range(F + 1, D):
        h = p.hw(bz, y)
        for lx in range(-h + 1, h):
            p.put(lx, y, bz, "minecraft:air" if lx == 0 and y in (F + 1, F + 2) else b["hull_high"])
    # the breach: drifted sand to one under the sand outside (its sill), then two rows of air and one over
    t = p.L - 1
    for lx in range(-p.w["breach_half"], p.w["breach_half"] + 1):
        sill = max(F, p.ground(lx, t + 1) - 1)
        for y in range(F + 1, sill + 4):
            p.put(lx, y, t, "minecraft:sand" if y <= sill else "minecraft:air")


def cabin(p):
    """The master's cabin over the berth: walls, a doorway from the deck, two broken stern windows, the roof (the poop
    deck) and its rail, a lantern over the stern."""
    b = p.doc["blocks"]
    D = p.D
    c0, ch = p.w["cabin"]["from"], p.w["cabin"]["height"]
    t = p.L - 1
    for lz in range(c0, p.L):
        h = p.hw0(lz)
        for lx in range(-h, h + 1):
            wall = abs(lx) == h or lz in (c0, t) or abs(lx) > p.hw0(lz + 1) if lz < t else True
            for y in range(D + 1, D + ch + 1):
                p.put(lx, y, lz, b["cabin"] if wall else "minecraft:air")
            p.put(lx, D + ch + 1, lz, b["deck"])
    for y in (D + 1, D + 2):
        p.put(0, y, c0, "minecraft:air")                        # the doorway; its door is gone
    for lx in (-2, 2):
        p.put(lx, D + 2, t, "minecraft:air")                    # the stern windows, broken
    # the poop deck's rail, a lantern on its stern post
    top = D + ch + 2
    ring = set()
    for lz in range(c0, p.L):
        h = p.hw0(lz)
        for lx in range(-h, h + 1):
            if abs(lx) == h or lz in (c0, t):
                ring.add((lx, lz))
    ring.discard((0, c0))                                        # the gap where the ladder from the deck would come
    for lx, lz in ring:
        p.put(lx, top, lz, fence(n=(lx, lz - 1) in ring, s=(lx, lz + 1) in ring, e=(lx + 1, lz) in ring,
                                 w=(lx - 1, lz) in ring))
    p.hang(0, top + 1, t, "minecraft:lantern[hanging=false,waterlogged=false]")
    return top + 1


def rail(p):
    """The rail along the deck's edge forward of the cabin, where the deck is clear of the dune (ground under it)."""
    D = p.D
    ring = set()
    for lz in range(0, p.w["cabin"]["from"]):
        h = p.hw0(lz)
        for lx in range(-h, h + 1):
            edge = abs(lx) == h or lz == 0 or abs(lx) > p.hw0(lz - 1)
            if edge and p.ground(lx, lz) <= D:
                ring.add((lx, lz))
    for lx, lz in ring:
        p.put(lx, D + 1, lz, fence(n=(lx, lz - 1) in ring, s=(lx, lz + 1) in ring, e=(lx + 1, lz) in ring,
                                   w=(lx - 1, lz) in ring))
    return ring


def weathering(p):
    """One deck plank in nine gone where the deck is open to the sky (the ground under it), none where the dune lies
    on it: sand over a hole would fall into the hold."""
    D = p.D
    keep = {(0, p.w["hatch_at"]), (0, p.w["masts"]["main"]["at"]), (0, p.w["masts"]["fore"]["at"])}
    holes = []
    for lz in range(1, p.w["cabin"]["from"]):
        h = p.hw0(lz)
        for lx in range(-h + 1, h):
            x, z = p.xz(lx, lz)
            if (lx, lz) in keep or p.ground(lx, lz) >= D or lz <= p.w["hold"]["spill_slope_to"]:
                continue
            if _h(x, z, 7) % 9 == 0:
                p.put(lx, D, lz, "minecraft:air")
                holes.append((x, D, z))
    return holes


def masts(p):
    """The foremast out of the dune; the mainmast broken over its yard; the ladder and hatch at its foot."""
    b = p.doc["blocks"]
    D, F = p.D, p.floor
    m = p.w["masts"]
    tops = {}
    for k in ("fore", "main"):
        lz = m[k]["at"]
        for y in range(F, D + m[k]["top_over_deck"] + 1):
            p.put(0, y, lz, "%s[axis=y]" % b["mast"])
        tops[k] = D + m[k]["top_over_deck"]
    mz = m["main"]["at"]
    yy = D + m["main"]["yard_over_deck"]
    for lx in range(-m["main"]["yard_half"], m["main"]["yard_half"] + 1):
        if lx:
            p.put(lx, yy, mz, "%s[axis=x]" % b["mast"])
    hz = p.w["hatch_at"]
    for y in range(F + 1, D):
        p.hang(0, y, hz, "minecraft:ladder[facing=south,waterlogged=false]")
    p.hang(0, D, hz, "minecraft:spruce_trapdoor[facing=south,half=top,open=false,powered=false,waterlogged=false]")
    return tops


def cargo(p):
    """The hold: the ore that never sailed, barrels, pots, the company's plate, lanterns from the deck."""
    doc = p.doc
    D, F = p.D, p.floor
    spill_to = p.w["hold"]["spill_slope_to"]
    bz = p.w["bulkhead"]
    skip = {p.w["masts"]["main"]["at"], p.w["hatch_at"], p.w["hatch_at"] + 1}
    for lz in range(spill_to + 3, bz - 1):
        if lz in skip:
            continue
        for lx in (-3, 3):
            p.put(lx, F + 1, lz, "minecraft:raw_copper_block")
            if lz % 3 == 0:
                p.put(lx, F + 2, lz, "minecraft:raw_copper_block")
    for lz in (spill_to + 4, spill_to + 8, bz - 3):
        for lx in (-2, 2):
            p.put(lx, F + 1, lz, "minecraft:barrel[facing=up,open=false]")
    p.put(-2, F + 1, bz - 2, "minecraft:decorated_pot[cracked=true,facing=north,waterlogged=false]")
    p.put(2, F + 1, bz - 2, "minecraft:decorated_pot[cracked=false,facing=north,waterlogged=false]")
    p.hang(2, F + 3, bz - 1, wall_sign("north", doc["signs"]["hold"]))
    lights = [(0, spill_to + 4), (-2, p.w["masts"]["main"]["at"] - 1), (0, bz - 3)]
    for lx, lz in lights:
        p.hang(lx, D - 1, lz, "minecraft:lantern[hanging=true,waterlogged=false]")
    return lights


def berth(p):
    """The crew's berth under the cabin: their bedding (carpets: no bed sets a respawn), lockers, a lantern."""
    D, F = p.D, p.floor
    c0 = p.w["cabin"]["from"]
    for lz in range(c0 + 1, c0 + 4):
        for lx in (-3, -2, 2, 3):
            p.hang(lx, F + 1, lz, "minecraft:light_gray_carpet")
    for lx in (-3, 3):
        p.put(lx, F + 1, c0 + 6, "minecraft:barrel[facing=up,open=false]")
    p.put(-3, F + 1, c0 + 7, "minecraft:decorated_pot[cracked=true,facing=east,waterlogged=false]")
    p.hang(0, D - 1, c0 + 4, "minecraft:lantern[hanging=true,waterlogged=false]")


def cabin_fittings(p):
    """The master's cabin: the log on the port wall, the lectern, the chart table, the sea chest, a lantern."""
    doc = p.doc
    D = p.D
    c0 = p.w["cabin"]["from"]
    for k, lz in enumerate((c0 + 1, c0 + 3, c0 + 5, c0 + 7)):
        p.hang(-p.hw0(lz) + 1, D + 2, lz, wall_sign("east", doc["signs"]["log_%d" % (k + 1)]))
    p.put(0, D + 1, c0 + 7, "minecraft:lectern[facing=north,has_book=false,powered=false]")
    p.put(-3, D + 1, c0 + 7, "minecraft:cartography_table")
    bx, bz = doc["find"]["barrel_local"]
    p.put(bx, D + 1, bz, "minecraft:barrel[facing=west,open=false]")
    for lz in range(c0 + 2, c0 + 6):
        for lx in (-1, 0, 1):
            p.hang(lx, D + 1, lz, "minecraft:blue_carpet")
    p.hang(0, D + p.w["cabin"]["height"], c0 + 4, "minecraft:lantern[hanging=true,waterlogged=false]")


def spar(p):
    """The mainmast's top, lying on the flats east of the hull, each log on its own ground + 1."""
    s = p.doc["spar"]
    cx, cz = p.doc["site"]["centre"]
    x0, z = p.W + s["from"][0], cz + s["from"][1]
    out = []
    for i in range(s["length"]):
        x = x0 + i
        y = p.g(x, z) + 1
        p.put_at(x, y, z, "%s[axis=x]" % p.doc["blocks"]["mast"])
        out.append((x, y, z))
    return out


def anchor(p):
    """The kedge's chain from the starboard quarter to the tide line, its anchor at the end."""
    a = p.doc["anchor"]
    x = p.W + a["chain_x"]
    out = []
    for z in range(p.Z0 + a["from_lz"], a["to_z"]):
        y = p.g(x, z) + 1
        p.put_at(x, y, z, "minecraft:chain[axis=z,waterlogged=false]")
        out.append((x, y, z))
    y = p.g(x, a["to_z"]) + 1
    p.put_at(x, y, a["to_z"], "minecraft:chipped_anvil[facing=east]")
    out.append((x, y, a["to_z"]))
    return out


def resident_spot(doc):
    r = doc["residents"][0]
    cx, cz = r["site"]["centre"]
    return cx + r["pokemon"]["at"][0], cz + r["pokemon"]["at"][1]


def reef(p):
    """Heads of dead coral, bone and calcite on the flats, one block awash where the ground is just under the sea."""
    doc = p.doc
    rf = doc["reef"]
    b = doc["blocks"]
    cx, _cz = doc["site"]["centre"]
    x0, x1 = cx + rf["x"][0], cx + rf["x"][1]
    z0, z1 = rf["z"]
    G = rf["grid"]
    chain_x = p.W + doc["anchor"]["chain_x"]
    rx, rz = resident_spot(doc)
    lo, t2, t3 = rf["threshold"], rf["tall"][0], rf["tall"][1]
    cols = {}
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge = min(x - x0, x1 - x, z - z0)                 # thinning out towards the reef's land edges
            v = noise(x, z, G) + ((_h(x, z, 13) % 100) / 100.0 - 0.5) * 0.12 - 0.3 * max(0.0, 1 - edge / 6.0)
            if v >= lo:
                cols[(x, z)] = 1 + (v >= t2) + (v >= t3)
    out = []
    for (x, z), hh in sorted(cols.items()):
        if abs(x - p.W) <= rf["lane_half"] or abs(x - chain_x) <= rf["chain_clear"]:
            continue
        if math.hypot(x - rx, z - rz) <= rf["resident_clear"]:
            continue
        g = p.g(x, z)
        if g < SEA - 1:
            continue                                     # deeper than one block: the reef stops at the shelf's edge
        if g < SEA:
            hh = 1                                       # awash: one block at the sea's surface, nothing on it
        for k in range(1, hh + 1):
            p.put_at(x, g + k, z, _pick(b["reef"], x, z * 31 + k, 3))
            out.append((x, g + k, z))
        if g >= SEA and _h(x, z, 5) % 3 == 0:
            p.hang_at(x, g + hh + 1, z, _pick(b["reef_tops"], x, z, 9))
            out.append((x, g + hh + 1, z))
    return out


def flag(p):
    """Castellan's flag: a white banner on a spruce fence post by the castle's spot."""
    r = p.doc["residents"][0]
    cx, cz = r["site"]["centre"]
    x, z = cx + r["flag"]["at"][0], cz + r["flag"]["at"][1]
    y = p.g(x, z)
    p.put_at(x, y + 1, z, fence())
    p.hang_at(x, y + 2, z, "minecraft:white_banner[rotation=8]")
    return [(x, y + 1, z), (x, y + 2, z)]


def plan(doc, g):
    p = Plan(doc, g)
    hull(p)
    spill(p)
    bulkhead_and_breach(p)
    tops = masts(p)
    lantern_top = cabin(p)
    ring = rail(p)
    holes = weathering(p)
    lights = cargo(p)
    berth(p)
    cabin_fittings(p)
    wreck_cells = set(p.blocks())
    sp = spar(p)
    an = anchor(p)
    rf = reef(p)
    fl = flag(p)
    blocks = p.blocks()
    strand = set(fl)

    def box(cells):
        xs, ys, zs = zip(*cells)
        return {"min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]}
    bx, bz = doc["find"]["barrel_local"]
    barrel = (p.W + bx, p.D + 1, p.Z0 + bz)
    t = p.L - 1
    outside = [p.ground(lx, t + 1) for lx in range(-p.w["breach_half"], p.w["breach_half"] + 1)]
    return {"plan": p, "D": p.D, "K": p.K, "floor": p.floor, "masts": tops, "stern_lantern": lantern_top,
            "rail": ring, "holes": holes, "lights": lights, "spar": sp, "anchor": an, "reef": rf, "flag": fl,
            "blocks": blocks, "wreck_cells": wreck_cells, "breach_outside_ground": outside,
            "bounds": {"wreck": box([k for k in blocks if k not in strand]), "strand": box(list(strand))},
            "barrel": barrel,
            "trigger": {"min": [barrel[0] - 1, barrel[1], barrel[2] - 1], "max": [barrel[0] + 1, barrel[1] + 1, barrel[2] + 1]},
            "resident": resident_anchor(doc, g), "wards": wards(doc, p)}


def resident_anchor(doc, g):
    x, z = resident_spot(doc)
    return x, g(x, z) + 1, z


def wards(doc, p):
    """[(id, (x, y, z), range)]: the natural Habitat Blocks, each one block under the ground or the keel."""
    out = []
    cx, cz = doc["site"]["centre"]
    for b in doc["pool"]["blocks"]:
        if b["where"] == "reef":
            x, z = cx + b["at"][0], cz + b["at"][1]
            out.append((b["id"], (x, p.g(x, z) - b["below_ground"], z), b["range"]))
        elif b["where"] == "keel":
            x, z = p.xz(0, b["lz"])
            out.append((b["id"], (x, p.K - b["below_keel"], z), b["range"]))
        else:
            raise WreckError("pool block %s: where must be reef or keel" % b["id"])
    return out


# ---------------------------------------------------------------------------------------------------------- checks
PASSABLE = ("minecraft:air", "minecraft:lantern", "minecraft:ladder", "minecraft:blue_carpet",
            "minecraft:light_gray_carpet", "minecraft:spruce_wall_sign")


def dark_cells(pl):
    """The air cells the pack writes that no lantern lights: block light spreads from 15 at each lantern, one less per
    step through air (and the carpets, signs and ladder light passes), and a cell at 0 is where a monster may spawn.
    Sky light is not counted, so a cell open to the sky must still be lit from a lantern if it is written air."""
    blocks = pl["blocks"]
    open_ = {k for k, s in blocks.items() if base(s) in PASSABLE}
    level = {}
    frontier = [k for k, s in blocks.items() if base(s) == "minecraft:lantern"]
    for k in frontier:
        level[k] = 15
    while frontier:
        nxt = []
        for (x, y, z) in frontier:
            v = level[(x, y, z)] - 1
            if v <= 0:
                continue
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (x + d[0], y + d[1], z + d[2])
                if n in open_ and level.get(n, 0) < v:
                    level[n] = v
                    nxt.append(n)
        frontier = nxt
    wc = pl["wreck_cells"] - set(pl["holes"])          # a deck hole is open to the sky, as the deck round it is
    return {k for k, s in blocks.items() if s == "minecraft:air" and k in wc and level.get(k, 0) <= 0
            and k[1] < pl["D"] + 1 + pl["plan"].w["cabin"]["height"] + 1}
def problems(doc, pl, g):
    """The builder's guards (not an audit): what the plan must hold, as strings."""
    p = pl["plan"]
    out = []
    D, K = p.D, p.K
    # the bow buried to the rail, the keel buried along her whole length, the stern standing on the flats
    bow = [p.ground(lx, lz) for lz in range(0, 3) for lx in range(-p.hw0(lz), p.hw0(lz) + 1)]
    if min(bow) < D + 1:
        out.append("the bow is not buried to the rail: ground over the bow's first 3 rows is %d, the rail D+1 is %d"
                   % (min(bow), D + 1))
    hull_cols = {(lx, lz) for lz in range(p.L) for lx in range(-p.hw0(lz), p.hw0(lz) + 1)}
    low = min(p.ground(lx, lz) for lx, lz in hull_cols)
    if low <= K:
        out.append("the keel shows: ground %d under the hull is not over the keel y%d" % (low, K))
    wet = [(lx, lz) for lx, lz in hull_cols if p.ground(lx, lz) < SEA]
    if wet:
        out.append("%d hull columns stand in the sea" % len(wet))
    # the way in: one step from the sand in front of the transom to the berth's floor
    for go in pl["breach_outside_ground"]:
        sill = max(p.floor, go - 1)
        if not (sill - p.floor <= 1 and go - sill <= 1) or sill + 3 >= D - 1:
            out.append("the breach is not one step each way: sand outside y%d, sill y%d, berth floor y%d"
                       % (go, sill, p.floor))
    # no air or sand where the sea stands; nothing written in deep water
    for (x, y, z), st in pl["blocks"].items():
        gy = g(x, z)
        if gy < SEA and (base(st) in ("minecraft:air", "minecraft:sand") or gy < SEA - 1):
            out.append("(%d, %d, %d) %s written in the sea" % (x, y, z, base(st)))
            break
    # every block allowed, none forbidden
    bad = sorted({base(s) for s in pl["blocks"].values()} & FORBIDDEN)
    if bad:
        out.append("forbidden blocks written: %s" % bad)
    # the resident's spot: dry, at the tide line, clear of the build
    ax, ay, az = pl["resident"]
    if g(ax, az) < SEA:
        out.append("Castellan's spot (%d, %d) is in the sea" % (ax, az))
    if not any(g(ax + dx, az + dz) < SEA for dx in range(-3, 4) for dz in range(-3, 4)):
        out.append("Castellan's spot (%d, %d) is not at the tide line (no sea within 3)" % (ax, az))
    for d in (0, 1):
        if (ax, ay + d, az) in pl["blocks"]:
            out.append("Castellan's spot is built on")
    # the natural wards: no two ranges overlap (EXP-021), each not in a block this pack writes
    ws = pl["wards"]
    for i in range(len(ws)):
        if ws[i][1] in pl["blocks"]:
            out.append("ward %s sits in a block the pack writes" % ws[i][0])
        for j in range(i + 1, len(ws)):
            d = math.dist(ws[i][1], ws[j][1])
            if d < ws[i][2] + ws[j][2]:
                out.append("wards %s and %s overlap: %.1f apart, ranges %d + %d" % (ws[i][0], ws[j][0], d, ws[i][2], ws[j][2]))
    # lit only by lanterns, and lit everywhere inside: no air cell the pack writes is at block light 0
    dark = dark_cells(pl)
    if dark:
        out.append("%d air cells inside the wreck are dark (block light 0), e.g. %s" % (len(dark), sorted(dark)[:3]))
    # the spawn conditions written are the ones declared
    try:
        spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    except (OSError, ValueError, KeyError):
        spawn = set()
    written = {base(s) for s in pl["blocks"].values()}
    undeclared = sorted((written & spawn) - set(doc["blocks"]["spawn_conditions"]))
    if undeclared:
        out.append("spawn conditions written and not declared in blocks.spawn_conditions: %s" % undeclared)
    return out


# ---------------------------------------------------------------------------------------------------------- the pack
def _runs(blocks, top_down=False):
    """setblock and fill lines for {(x, y, z): state}, one fill per run of one state along x, bottom up (or top down)."""
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


def clear_box(pl):
    """(x0, y0, z0, x1, y1, z1): everything written, its margin, from the lowest ground up past the highest block."""
    p = pl["plan"]
    b = pl["bounds"]
    x0 = min(b["wreck"]["min"][0], b["strand"]["min"][0]) - CLEAR_MARGIN
    z0 = min(b["wreck"]["min"][2], b["strand"]["min"][2]) - CLEAR_MARGIN
    x1 = max(b["wreck"]["max"][0], b["strand"]["max"][0]) + CLEAR_MARGIN
    z1 = max(b["wreck"]["max"][2], b["strand"]["max"][2]) + CLEAR_MARGIN
    low = min(max(p.g(x, z), SEA - 1) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    top = max(b["wreck"]["max"][1], b["strand"]["max"][1]) + CLEAR_OVER
    return x0, low + 1, z0, x1, top, z1


def build_lines(doc, pl):
    p = pl["plan"]
    out = ["# Generated by tools/desert_wreck.py from data/desert_wreck.json. Re-run to rebuild; do not edit.",
           "# The Brass Petrel: the wreck in the dune wall, the dead reef, the castle's flag. Run as R9DW, before R9E.",
           "# 1. clear the beach's plants over everything this writes (named blocks only: #minecraft:replaceable holds water)"]
    x0, y0, z0, x1, y1, z1 = clear_box(pl)
    for tag in PLANTS:
        out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, bottom up, in one function: the deck is in before the tick in which sand over it could fall")
    out += _runs(p.solid)
    out.append("# 3. what hangs on it or stands on it, from the top: lanterns, signs, ladder, trapdoor, carpets, sprigs, banner")
    out += _runs(p.hung, top_down=True)
    return out


def files(doc, g):
    """{relative path: text} of the pack, and the plan. The resident's keeper is tools/resident_encounters.py's."""
    import resident_encounters as RE
    import southern_residents as SR
    pl = plan(doc, g)
    probs = problems(doc, pl, g)
    if probs:
        raise WreckError("desert_wreck: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    lines = function_limits.ensure_loaded(build_lines(doc, pl))
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise WreckError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    fn = {"build": lines}
    sh = SR.shim(doc)
    load_ = ["# the Brass Petrel's strand keeper state (tools/desert_wreck.py, on tools/resident_encounters.py's keeper).",
             "# A clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
             "scoreboard objectives add %s dummy" % obj,
             "scoreboard players set #resp %s %d" % (obj, int(b["respawn_ticks"])),
             "execute store result score #ready %s run time query gametime" % obj,
             "scoreboard players operation #ready %s -= #resp %s" % (obj, obj)]
    keeper = ["execute store result score #now %s run time query gametime" % obj]
    box = resident_box(pl)
    for r in doc["residents"]:
        e = SR.resident_record(r)
        a = pl["resident"]
        i = e["id"]
        rf = RE.resident_files(sh, e, a, [], [], box)
        rf.pop("%s/dress" % i, None)
        fn.update(rf)
        load_ += ["execute unless score #%s.gone %s matches -2147483648.. run scoreboard players operation #%s.gone %s = #ready %s"
                  % (i, obj, i, obj, obj),
                  "execute unless score #%s.abs %s matches -2147483648.. run scoreboard players set #%s.abs %s 0" % (i, obj, i, obj)]
        keeper.append("execute if loaded %d %d %d run function %s:%s/%s/keep" % (a[0], a[1], a[2], ns, F, i))
    fn["spawn_at"] = ["# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
                      "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
    load_.append("schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"]))
    keeper.append("schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"]))
    fn["load"] = load_
    fn["keeper"] = keeper
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, F, n): "\n".join(v) + "\n" for n, v in fn.items()}
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, F)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: the Brass Petrel on the southern desert beach (tools/desert_wreck.py)"}},
                                    indent=2) + "\n"
    return out, pl


def resident_box(pl):
    """[x0, z0, x1, z1]: the resident's leash round its anchor (the keeper's dressing is empty: R18 force-loads nothing)."""
    ax, _ay, az = pl["resident"]
    lz = pl["plan"].doc["residents"][0]["pokemon"]["leash"]
    return [ax - lz, az - lz, ax + lz, az + lz]


def hold_box(pl):
    x0, _y0, z0, x1, _y1, z1 = clear_box(pl)
    return x0, z0, x1, z1


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, as R9DW BEFORE R9E with the other block passes: hold the chunks, build, release."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    pl = plan(doc, g)
    b = doc["build"]
    hold = "%d %d %d %d" % hold_box(pl)
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (b["namespace"], b["folder"])),
            ("cmd", "forceload remove " + hold)]


def entity_steps(doc=None, g=None):
    """Empty by design: the one resident is gated (appears_after), so its keeper brings it in; nothing is summoned."""
    doc = doc or load()
    if not all(r["pokemon"].get("appears_after") for r in doc["residents"]):
        raise WreckError("an ungated resident needs an RCON summon step (tools/far_south.py entity_steps); none is written")
    return []


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------------------------------------------- the records
def records(doc, pl, positions=None):
    """(habitat block records, the pool {habitat, entries}, the reward record) this place owns in the shared files.
    `positions` is {species: spawnable position}; without it, each entry's position is read from data/spawns.json's
    own copy of this pool (so the records can be compared without the jar)."""
    pool = doc["pool"]
    pid = pool["id"]
    lo, hi = pool["band"]
    level = "%d-%d" % (lo, hi)
    habs = []
    for bid, (x, y, z), rng in pl["wards"]:
        where = next(b for b in pool["blocks"] if b["id"] == bid)["where"]
        habs.append({
            "id": bid,
            "place": "the Brass Petrel on the southern desert beach (data/desert_wreck.json): %s" % (
                "one block under the sand in the middle of the dead reef" if where == "reef"
                else "one block under the keel, under the sand-choked forepeak"),
            "pool": "cobblers:%s" % pid,
            "style": "natural",
            "replace_spawns": True,
            "range_of_influence": rng,
            "position": {"x": x, "y": y, "z": z},
            "status": "planned",
            "why": "written by tools/desert_wreck.py records --write from the plan (data/desert_wreck.json pool.blocks): "
                   "inside its range every ambient spawn is drawn from the strand's pool instead of the pack's "
                   "defaults (EXP-021; the vertical shape is EXP-033, unrun). Not in a block the pack writes, so R9E "
                   "may run before or after R9DW. Inert until its chunk reloads: restart after R9E."})
    old = {e["species"]: e.get("spawnable_position") for e in
           json.loads(SPAWNS.read_text(encoding="utf-8"))["entries"] if e.get("scope") == pid}
    rar = json.loads(SPAWNS.read_text(encoding="utf-8"))["rarity"]
    hab_entries, entries = [], []
    for row in pool["entries"]:
        sp, role, why = row[0], row[1], row[2]
        fam = row[3] if len(row) > 3 else sp
        ao = role == "authored-only"
        bucket = "authored-only" if ao else rar[role]["bucket"]
        weight = 0 if ao else rar[role]["family_weight"]
        pos = (positions or {}).get(sp) or old.get(sp) or "grounded"
        display = " ".join(w.capitalize() for w in reversed(sp.split())) if " " in sp else sp.capitalize()
        hab_entries.append({"species": display, "pokemon": sp, "family": fam,
                            "family_priority": next(r[1] for r in pool["entries"] if r[0] == fam),
                            "ambient": not ao, "eligibility_reason": why, "level": level, "bucket": bucket,
                            "weight": weight, "conditions": {}})
        entries.append({"id": "habitat.%s.%s" % (pid, sp.replace(" ", "_")), "species": sp,
                        "bucket": "ultra-rare" if ao else bucket, "level": level, "weight": weight, "ambient": not ao,
                        "scope": pid, "mechanism": "habitat_block", "conditions": {}, "eligibility_reason": why,
                        "spawnable_position": pos})
    habitat = {"id": pid, "display_name": pool["display_name"],
               "intended_location": "the southern desert beach round the Brass Petrel (%d, %d): two natural "
                                    "ReplaceSpawns Habitat Blocks, %s in data/habitat_blocks.json"
                                    % (doc["site"]["centre"][0], doc["site"]["centre"][1],
                                       " and ".join(b["id"] for b in pool["blocks"])),
               "mechanism": "habitat_block", "replace_spawns": True,
               "level_band": {"minimum": lo, "maximum": hi}, "level_band_why": pool["band_why"],
               "why": pool["entries_why"], "entries": hab_entries,
               "placement_status": "authored: data/habitat_blocks.json %s, status planned"
                                   % ", ".join(b["id"] for b in pool["blocks"])}
    f = doc["find"]
    reward = {"id": f["reward"], "kind": "cache",
              "place": "the Brass Petrel on the southern desert beach: the master's sea chest in the stern cabin",
              "contents": [{"item": it, "count": n,
                            "verification": "assets/cobblemon/models/item/%s.json in Cobblemon-fabric-1.8.0+1.21.1.jar"
                                            % it.split(":", 1)[1]} for it, n in f["contents"]],
              "message": f["message"], "why": f["why"],
              "built_by": "tools/desert_wreck.py (the barrel, in cobblers_desert_wreck's build, reapply step R9DW)",
              "trigger": pl["trigger"],
              "container": {"block": "minecraft:barrel", "at": list(pl["barrel"])}}
    return habs, {"habitat": habitat, "entries": entries}, reward


def jar_positions(doc):
    """{species: spawnable position} from the Cobblemon jar's own spawn files (tools/position_types.py choose())."""
    import battle_sim
    import position_types as PT
    up = PT.upstream_positions(battle_sim.find_jar())
    return {row[0]: PT.choose(row[0], up)[0] for row in doc["pool"]["entries"]}


def write_records(habs, pool, reward):
    def dump(path, d):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    hd = json.loads(HABITATS.read_text(encoding="utf-8"))
    ids = {h["id"] for h in habs}
    hd["blocks"] = [b for b in hd["blocks"] if b.get("id") not in ids] + habs
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    pid = pool["habitat"]["id"]
    sd["habitats"] = [h for h in sd["habitats"] if h.get("id") != pid] + [pool["habitat"]]
    sd["entries"] = [e for e in sd["entries"] if e.get("scope") != pid] + pool["entries"]
    dump(HABITATS, hd)
    dump(SPAWNS, sd)
    # data/rewards.json is hand-formatted (compact trigger lines), so a re-dump would rewrite every record: the
    # reward goes in as text, replacing its own record if there is one, appended at the end of the list if not
    text = REWARDS.read_text(encoding="utf-8")
    want = json.loads(text)
    want["rewards"] = [r for r in want["rewards"] if r.get("id") != reward["id"]] + [reward]
    rec = "\n".join("    " + ln for ln in json.dumps(reward, indent=2, ensure_ascii=False).splitlines())
    lines = text.split("\n")
    key = '      "id": "%s",' % reward["id"]
    if key in lines:
        i = lines.index(key) - 1
        j = i
        while lines[j] not in ("    },", "    }"):
            j += 1
        comma = "," if lines[j].endswith(",") else ""
        lines[i:j + 1] = (rec + comma).split("\n")
        text = "\n".join(lines)
    else:
        end = text.rindex("\n  ]\n}")
        text = text[:end] + ",\n" + rec + text[end:]
    if json.loads(text) != want:
        raise WreckError("data/rewards.json: the text insertion does not parse to the intended records")
    with open(REWARDS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------------------------------------------------- the CLI
def report(doc, pl, g):
    import southern_residents as SR
    import numpy as np
    p = pl["plan"]
    b = pl["blocks"]
    cx, cz = doc["site"]["centre"]
    pts = SR.authored_points({"residents": []}, own_file=DATA)
    P = np.array([(a, c) for a, c, _f in pts], float)
    d = np.hypot(P[:, 0] - cx, P[:, 1] - cz)
    places = [i for i in np.argsort(d) if pts[i][2] != "regions.json"]
    near = pts[places[0]]
    paths = np.array([q for pl_ in SR.jload("route_paths.json")["paths"].values() for q in pl_], float)
    dp = float(np.min(np.hypot(paths[:, 0] - cx, paths[:, 1] - cz)))
    ws = pl["wards"]
    lines = ["site %s: deck D y%d (transom sand y%d + %d), keel y%d, hold floor y%d; masts %s; stern lantern y%d"
             % (doc["site"]["centre"], p.D, p.D - p.w["stern_show"], p.w["stern_show"], p.K, p.floor, pl["masts"],
                pl["stern_lantern"]),
             "blocks written: %d (air %d, sand %d, reef %d); deck holes %d; rail posts %d"
             % (len(b), sum(1 for s in b.values() if s == "minecraft:air"),
                sum(1 for s in b.values() if s == "minecraft:sand"), len(pl["reef"]), len(pl["holes"]), len(pl["rail"])),
             "bounds: %s" % json.dumps(pl["bounds"]),
             "breach: sand outside y%s, berth floor y%d" % (pl["breach_outside_ground"], p.floor),
             "Castellan: anchor %s; flag %s" % (list(pl["resident"]), pl["flag"]),
             "wards: %s; apart %.1f" % ([(i, list(xyz), r) for i, xyz, r in ws],
                                        math.dist(ws[0][1], ws[1][1]) if len(ws) > 1 else 0),
             "find: barrel %s, trigger %s" % (list(pl["barrel"]), json.dumps(pl["trigger"])),
             "nearest authored place (not a regions.json vertex): %.0f blocks, (%d, %d) in data/%s; nearest route path %.0f"
             % (d[places[0]], near[0], near[1], near[2], dp),
             "steps (R9DW, before R9E): %s" % json.dumps([list(s) for s in placement_steps(doc, g)])]
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "report", "records"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true", help="records: replace this place's records in the three files")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.cmd == "records":
        pl = plan(doc, g)
        habs, pool, reward = records(doc, pl, jar_positions(doc))
        if a.write:
            write_records(habs, pool, reward)
            print("desert_wreck: wrote %d habitat blocks, 1 pool with %d entries, 1 reward" % (len(habs), len(pool["entries"])))
        else:
            print(json.dumps({"habitat_blocks": habs, "pool": pool, "reward": reward}, indent=1))
        return 0
    out_files, pl = files(doc, g)
    if a.cmd == "report":
        print("\n".join(report(doc, pl, g)))
        return 0
    write(out_files, a.out)
    n = sum(1 for l in out_files["data/%s/function/%s/build.mcfunction" % (doc["build"]["namespace"], doc["build"]["folder"])]
            .splitlines() if l and not l.startswith("#"))
    print("desert_wreck: %d files -> %s (build: %d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
