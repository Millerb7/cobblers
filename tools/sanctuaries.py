#!/usr/bin/env python
"""The legendary sanctuaries (data/sanctuaries.json): open-air set pieces that replace the cave kit's K2-K6 (the owner,
2026-10-12, after walking up to one: "I hate the cave look, it feels out of place, and the inside being a small tunnel to a
legendary feels worse. Need a different solution than a cave." and "we don't need the non-legendaries, just make something that
looks good"). K1 (Stoneford Cut, Gible's power line) is retired with no successor.

  S2 The Singing Hollow   Meloetta: a ruined open-air theatre, its tall stage front the door, the cavea round a sunken orchestra
  S3 The Broken Relay     Miraidon: a fenced relay compound on Mt Vessu's shoulder under a snapped copper lattice mast
  S4 The Tide Shrine      Tapu Fini and Nihilego: a ring of sea-stone monoliths round a tide-pool court, a gate of two posts
  S5 The Stopped Clock    Dialga: a walled court of stopped sundials under a ruined clock tower
  S6 Sunscar              Koraidon: an oval sun arena of red sandstone half-buried in the cinder of the east cones

What a sanctuary is, for every system that reads one: an enclosed COURT (the old cave's chamber: the occupant's Habitat Block or the
boss's spot is its centre floor cell), a wall round it that no player on foot can step or jump over (a walk proves it), one DOOR in
that wall (the cave kit's barrier partition: tools/caves.py's gate, open while a flagged player stands in the FORECOURT, the old
antechamber), and the set piece's own dressing round it. It stands on a level platform at the median of the canonical heightmap
over its footprint (never a world: CLAUDE.md "Ground comes from the heightmap"), with a graded band round the platform so the land
runs into it at no more than one block a step.

What it reuses, by name (CLAUDE.md principle 6):

  the cell engine        tools/caves.py's: {(x, y, z): block} written as vertical runs by tools/mines.py column_runs, in tools/mines.py
                         frame()'s (u, d) axes; hashes by tools/mines.py h32/sid
  siting and clearance   tools/mining_caves.py Clearance, as tools/caves.py uses it (towns, legs and paths, corridor boxes, authored
                         x/z, earthworks and templates, other packs' writes, painted water and trees, the water export)
  the gate and keeper    tools/caves.py's partition gate and area-boss keeper (tools/drowned_quarry.py keeper_files' shape), moved here
                         with their rules unchanged: one tagged dormant alpha, 24,000 ticks back after a faint and 72,000 after a
                         catch, spawned only for a player holding the gate flag, never touching a blackout guardian (C25)
  the restore            tools/legendaries.py retired_sites and terrain_lines; tools/rift_zones.py gatehouse.legacy: every column a
                         retired cave wrote goes back to the heightmap's terrain, run only while the cave still stands, refused
                         while a player stands in one of its voids, BEFORE the sanctuary is built over it

  python tools/sanctuaries.py site <id> [--top N]   candidate sites, best first; nothing written
  python tools/sanctuaries.py author [<id>] [--resite]   site what has no site yet; write data/sanctuaries.json and the derived
                                                    records (data/habitat_blocks.json, data/spawns.json, data/world_probes.json)
  python tools/sanctuaries.py report                every sanctuary's checks; nothing written
  python tools/sanctuaries.py render [--out DIR]    elevation and plan images of every set piece (derived/sanctuaries/)
  python tools/sanctuaries.py build                 -> build/datapacks/cobblers_sanctuaries, derived/sanctuaries/plan.json

  --inputs-root <full checkout>   where build/datapacks, build/paint, derived/routes and derived/water_shape are read

What this does NOT cover (CLAUDE.md "Our list is not the world"): the keeper and gate act only on data/sanctuaries.json's records.
The restore puts back only the retired caves' own cells; whatever another system wrote into those columns since R9CK (none is
known) is put back to terrain with them. A player who flies or pillars over a wall stands in a court without the flag: the keeper
still never spawns for them and the level cap is the real gate, as it was for a player who dug through a cave's shell.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402
import mines as M              # noqa: E402
import mining_caves as MC      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "sanctuaries.json"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
PROBES = ROOT / "data" / "world_probes.json"
REGIONS = ROOT / "data" / "regions.json"
LEGENDARIES = ROOT / "data" / "legendaries.json"
PROGRESSION = ROOT / "data" / "progression.json"
PACK = "cobblers_sanctuaries"
OUT = ROOT / "build" / "datapacks" / PACK
PLAN = ROOT / "derived" / "sanctuaries" / "plan.json"
RENDERS = ROOT / "derived" / "sanctuaries"
NS = "cobblers"
FOLDER = "sanctuaries"
F = "%s:%s" % (NS, FOLDER)
AIR = "minecraft:air"
BARRIER = "minecraft:barrier"
WATER = "minecraft:water"
LANTERN_UP = "minecraft:lantern[hanging=false,waterlogged=false]"
LANTERN_HANG = "minecraft:lantern[hanging=true,waterlogged=false]"
PRESENT = -2147483648     # a boss's clock: seen present
NEVER = -2147483647       # a boss's clock: never yet brought in
FRONTS = M.FRONTS
YAW = {"north": 180, "south": 0, "west": 90, "east": 270}   # facing the door, down -d: Minecraft yaw 0 is south, 90 west
STYLES = ("amphitheatre", "relay", "tide_shrine", "clock_court", "sun_arena")
MODES = ("rare_spawn", "area_boss")
GENERATED = "tools/sanctuaries.py"
POLICY_SCOPE = "sanctuaries"
CHUNK_OBJ = "cobblers_chunk_look"    # tools/chunk_look.py OBJ: tools/reapply.py's ("check", ("chunk_look", ...)) reads it
HELD = "cobblers_sanct_restore_held"  # worn by a player standing in a retired cave's void: its restore refused
# ground: the functions that read a world, each only to check (tools/ground_rule.py); this tool reads none
WORLD_READS: set = set()


class SanctuaryError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def base(block):
    return block.split("[")[0].split("{")[0]


def species_id(name):
    return name.lower().replace(" ", "")


def pool_of(h):
    return h["pool"]["id"]


# ------------------------------------------------------------------ the local frame

def dirs(front):
    """{token: world facing} for a sanctuary entered from `front` (tools/mines.py frame: d runs away from the door)."""
    xz = M.frame((0, 0), front)

    def name(v):
        return {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}[v]
    o = xz(0, 0)
    din = (xz(0, 1)[0] - o[0], xz(0, 1)[1] - o[1])
    dright = (xz(1, 0)[0] - o[0], xz(1, 0)[1] - o[1])
    t = {"in": name(din), "out": name((-din[0], -din[1])), "right": name(dright), "left": name((-dright[0], -dright[1]))}
    t["axd"] = "x" if din[0] else "z"
    t["axu"] = "x" if dright[0] else "z"
    return t


def resolve(block, toks):
    for k, v in toks.items():
        block = block.replace("{%s}" % k, v)
    if "{" in block.split("[")[0] or ("[" in block and "{" in block.split("[", 1)[1]):
        raise SanctuaryError("unresolved token in %s" % block)
    return block


def dilate8(cells, n=1):
    out = set(cells)
    for _ in range(n):
        out |= {(u + a, d + b) for (u, d) in out for a in (-1, 0, 1) for b in (-1, 0, 1)}
    return out


def ring_layers(cells):
    """The layer that seals every 4-neighbour of `cells`: dilate8(cells, 1) minus cells."""
    return dilate8(cells, 1) - set(cells)


def radial(u, d):
    """The world-token facing pointing away from the centre along the dominant axis."""
    if abs(u) >= abs(d):
        return "{right}" if u > 0 else "{left}"
    return "{in}" if d > 0 else "{out}"


# ------------------------------------------------------------------ the composition

class Piece:
    """One set piece in its local frame: (u, d) columns, h the height over the floor (h = 0 is the floor cell)."""

    def __init__(self, spec, san):
        self.spec, self.san = spec, san
        self.seed, self.fid = spec["seed"], M.sid(san["id"])
        self.pal = san["palette"]
        self.blocks = {}          # (u, d, h) -> block with tokens
        self.court = set()        # the enclosed interior (u, d)
        self.seal = set()         # the wall layer that seals the court (dilate8(court, 1) - court): never under wall_min but at the door
        self.wall = set()         # every wall column (the seal and any thicker or decorative layer)
        self.fore = set()         # the forecourt (the old antechamber): where a flagged player stands to open the door
        self.extra = set()        # other footprint columns at floor level (features, aprons)
        self.floor = {}           # (u, d) -> the block at h = 0
        self.door = []            # (u, d, h) of the door's air (the barrier row included)
        self.barrier = []         # (u, d, h): the closed door
        self.drift = {}           # (u, d) -> height of a graded drift on the platform (Sunscar's cinder)
        self.reach = san["court"]["reach"]

    def r(self, *k):
        return M.h32(self.seed, self.fid, *[int(v) for v in k]) / 4294967296.0

    def mix(self, name, *k):
        """A deterministic weighted pick from palette[name] ([[block, weight], ...] or a single block)."""
        e = self.pal[name]
        if isinstance(e, str):
            return e
        tot = sum(w for _b, w in e)
        x = self.r(M.sid(name), *k) * tot
        for b, w in e:
            x -= w
            if x < 0:
                return b
        return e[-1][0]

    def put(self, u, d, h, block):
        self.blocks[(u, d, h)] = block

    def col(self, u, d, h0, h1, name_or_block):
        for h in range(h0, h1 + 1):
            self.blocks[(u, d, h)] = self.mix(name_or_block, u, d, h) if name_or_block in self.pal else name_or_block

    def post(self, u, d, post_block, height=2):
        """A lantern on a post: `height` post blocks, the lantern standing on the top one (never a light block)."""
        for h in range(1, height + 1):
            self.blocks[(u, d, h)] = post_block
        self.blocks[(u, d, height + 1)] = LANTERN_UP
        self.extra.add((u, d))

    def footprint(self):
        return self.court | self.wall | self.fore | self.extra

    def noise(self, salt, t, octaves=((1, 1.0), (2, 0.5), (5, 0.25))):
        """Smooth periodic noise over an angle t (radians): seeded sines, about -1..1."""
        v = 0.0
        for k, a in octaves:
            v += a * math.sin(k * t + 6.2831853 * self.r(salt, k))
        return v / sum(a for _k, a in octaves)


def _door(p, cells_ud, bar_d, h_door):
    """Cut the door: air in every (u, d) of cells_ud for h 1..h_door, the barrier in the row d == bar_d."""
    for (u, d) in cells_ud:
        for h in range(1, h_door + 1):
            p.blocks[(u, d, h)] = BARRIER if d == bar_d else AIR      # built closed: the gate's near opens it for a flagged player
            p.door.append((u, d, h))
            if d == bar_d:
                p.barrier.append((u, d, h))


def _court_floor(p, name):
    for c in p.court:
        p.floor.setdefault(c, p.mix(name, c[0], c[1], 0))


def _clear(p, cells, h1=4):
    """Air over the floor of these columns where nothing is built (it lifts grass and flowers off a paved floor)."""
    for (u, d) in cells:
        for h in range(1, h1 + 1):
            p.blocks.setdefault((u, d, h), AIR)


# ---- S2: the theatre (Meloetta)

def amphitheatre(p):
    D = p.san["dims"]
    R, fr = D["court_r"], D["front_d"]
    I = {(u, d) for u in range(-R, R + 1) for d in range(fr, R + 1) if u * u + d * d < R * R}
    p.court |= I
    p.seal = ring_layers(I)
    W = dilate8(I, 2) - I
    fh = D["frons_half"]
    frons = {(u, d) for u in range(-fh, fh + 1) for d in (fr - 2, fr - 1)}
    p.wall |= W | frons
    ro, nt = D["orchestra_r"], D["tiers"]
    walk = ro + 2 * nt                      # the walkway behind the top tier
    # the ring: 2 thick, a blind arcade on its outer face, its crest broken
    for (u, d) in sorted(W):
        if d < fr:
            continue
        t = math.atan2(d, u)
        top = D["ring_h"] + round(1.6 * p.noise(1, t))
        if p.r(2, round(t * 20)) < 0.18:
            top -= 1
        lo = (D["ring_collapse"][0] <= math.degrees(t) <= D["ring_collapse"][1])
        if lo:
            top = D["ring_min"] + (1 if p.r(3, u, d) < 0.3 else 0)
        top = max(top, D["ring_min"])
        outer = (u, d) not in p.seal
        for h in range(1, top + 1):
            nm = "wall_low" if h <= 2 else "wall"
            p.put(u, d, h, p.mix(nm, u, d, h))
        p.put(u, d, top, p.mix("crest", u, d, top))
        # blind arches on the outer face every 6 degrees-ish: a recess 1 deep, h 2..4, keystone over it
        if outer and top >= 6 and round(math.degrees(t)) % 15 in (0, 1, 2) and not lo:
            for h in (2, 3, 4):
                p.put(u, d, h, AIR)
            p.put(u, d, 5, p.pal["keystone"])
    # the stage front (frons scaenae): two storeys of blind arches, a raised pediment at the middle, one end fallen
    for (u, d) in sorted(frons):
        au = abs(u)
        if au <= 5:
            top = D["frons_h"] + (5 - au) // 2
        elif au <= 12:
            top = D["frons_h"] - 3
        else:
            top = D["frons_h"] - 5
        if u > D["frons_fall_from"]:
            top = max(D["ring_min"] + 1, top - (u - D["frons_fall_from"]) - (1 if p.r(4, u) < 0.5 else 0))
        top += 1 if p.r(5, u, d) < 0.12 and au > 5 else 0
        outer = d == fr - 2
        for h in range(1, top + 1):
            p.put(u, d, h, p.mix("wall_low" if h <= 2 else "frons", u, d, h))
        if top >= 6 and au > 1:
            p.put(u, d, 6, p.pal["band"])           # a string course
        p.put(u, d, top, p.mix("crest", u, d, top))
        if outer and au > 2:
            if au % 4 == 0 and top >= 6:            # lower storey: tall blind arches
                for h in (2, 3, 4):
                    p.put(u, d, h, AIR)
                p.put(u, d, 5, p.pal["keystone"])
            if au % 4 == 2 and top >= 11:           # upper storey: smaller windows between them
                for h in (8, 9):
                    p.put(u, d, h, AIR)
                p.put(u, d, 10, p.pal["keystone"])
    # pilasters standing proud of the stage front between the lower arches
    for u in range(-fh, fh + 1):
        if abs(u) % 4 == 2 and abs(u) > 2:
            top = max(h for (uu, dd, h) in p.blocks if uu == u and dd == fr - 2 and p.blocks[(uu, dd, h)] != AIR) - 2
            top = min(top, 9)
            if top >= 3:
                for h in range(1, top + 1):
                    p.put(u, fr - 3, h, p.pal["column"])
                p.put(u, fr - 3, top, p.pal["capital"])
                p.extra.add((u, fr - 3))
    # the door: the stage front's middle arch (the porta regia), a keystone arch over it
    door = [(u, d) for u in (-1, 0, 1) for d in (fr - 2, fr - 1)]
    _door(p, door, fr - 2, D["door_h"])
    for u in (-2, -1, 0, 1, 2):
        p.put(u, fr - 2, D["door_h"] + 1, p.pal["keystone"])
    # inside: the orchestra floor, the raised stage, the cavea's seats
    for (u, d) in I:
        r = math.hypot(u, d)
        if r < ro:
            p.floor[(u, d)] = p.pal["ring"] if abs(r - 3.0) < 0.5 else (p.mix("orchestra", u, d, 0) if r >= ro - 1 else p.pal["orchestra_floor"])
        else:
            p.floor[(u, d)] = p.mix("paving", u, d, 0)
    for (u, d) in I:
        r = math.hypot(u, d)
        if d <= -2 and abs(u) <= D["stage_half"]:
            p.put(u, d, 1, p.pal["stage"])
            if d == -2 and math.hypot(u, -1) < ro:          # a step up onto the stage from the orchestra
                p.put(u, -1, 1, "%s[facing={out},half=bottom,shape=straight,waterlogged=false]" % p.pal["seat"])
            continue
        if d >= -1 and r >= ro:
            k = min(int((r - ro) // 2), nt)          # tier k (0..nt-1), nt the walkway
            h = k + 1
            for hh in range(1, h + 1):
                p.put(u, d, hh, p.mix("tier", u, d, hh))
            if k < nt and (r - ro) - 2 * k < 1.0:     # a seat's front edge: a stair whose back faces out
                p.put(u, d, h, "%s[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (p.pal["seat"], radial(u, d)))
            elif p.r(6, u, d) < 0.07 and h >= 2:      # a broken seat
                p.put(u, d, h, AIR)
            if p.r(7, u, d) < 0.10 and p.blocks.get((u, d, h)) != AIR:
                p.put(u, d, h + 1, p.pal["carpet"])
    _court_floor(p, "paving")
    _clear(p, I, 3)
    # the forecourt and its lantern posts; two lone columns, one fallen; rubble under the fallen end of the stage front
    f0, f1 = fr - 3 - D["forecourt_len"], fr - 3
    for u in range(-D["forecourt_half"], D["forecourt_half"] + 1):
        for d in range(f0, f1 + 1):
            p.fore.add((u, d))
            p.floor[(u, d)] = p.pal["path"] if abs(u) <= 1 else p.mix("paving", u, d, 0)
    _clear(p, p.fore, 3)
    for u in (-D["forecourt_half"] + 1, D["forecourt_half"] - 1):
        p.post(u, f1 - 1, p.pal["post"])
        p.post(u, f0 + 1, p.pal["post"])
    for (u, top) in ((-D["lone_u"], D["lone_h"]), (D["lone_u"], D["lone_h"] - 5)):
        d = f0 + 3
        p.put(u, d, 1, p.pal["plinth"])
        for h in range(2, top):
            p.put(u, d, h, p.pal["column"])
        p.put(u, d, top, p.pal["capital"] if u < 0 else p.pal["column"])
        p.extra.add((u, d))
    for d in range(f0 - 1, f0 + 5):                 # the fallen one, lying along the forecourt's far side
        u = D["lone_u"] + 2
        p.put(u, d, 1, p.pal["column"] if d < f0 + 4 else p.pal["capital"])
        p.extra.add((u, d))
    for k in range(10):                             # rubble below the fallen end
        u = D["frons_fall_from"] + 1 + int(p.r(8, k) * (fh - D["frons_fall_from"]))
        d = fr - 3 - int(p.r(9, k) * 3)
        p.put(u, d, 1, p.mix("rubble", u, d, 1))
        if p.r(10, k) < 0.4:
            p.put(u, d, 2, p.pal["rubble_slab"])
        p.extra.add((u, d))


# ---- S3: the relay compound (Miraidon)

def relay(p):
    D = p.san["dims"]
    H = D["court_half"]
    I = {(u, d) for u in range(-H, H + 1) for d in range(-H, H + 1) if abs(u) + abs(d) <= D["chamfer"]}
    p.court |= I
    p.seal = ring_layers(I)
    p.wall |= p.seal
    for (u, d) in sorted(p.seal):
        base_h = D["wall_h"]
        for h in range(1, base_h + 1):
            p.put(u, d, h, p.mix("wall", u, d, h))
        p.put(u, d, base_h, p.mix("wall_cap", u, d, base_h))
        pil = (u + d) % 4 == 0
        if pil:
            for h in range(base_h + 1, base_h + 3):
                p.put(u, d, h, p.pal["pilaster"])
            p.put(u, d, base_h + 3, p.pal["pilaster_cap"])
        else:
            for h in range(base_h + 1, base_h + 3):
                if p.r(11, u, d, h) > 0.16:          # bars missing here and there: the fence is old
                    p.put(u, d, h, p.pal["bars"])
    for (u, d) in I:
        p.floor[(u, d)] = p.mix("floor", u, d, 0)
    # a ring of copper inlay round the centre: where the boss stands
    for (u, d) in I:
        if 2.5 <= math.hypot(u, d) < 3.5:
            p.floor[(u, d)] = p.pal["inlay"]
    _clear(p, I, 4)
    # the gate: two pylons and a gantry over the door
    fd = -H - 1
    _door(p, [(u, fd) for u in (-1, 0, 1)], fd, D["door_h"])
    for u in (-2, 2):
        for h in range(1, D["gantry_h"] + 1):
            p.put(u, fd, h, p.pal["pylon"])
        p.put(u, fd, D["gantry_h"] + 1, p.pal["pilaster_cap"])
    for u in (-1, 0, 1):
        for h in range(D["door_h"] + 1, D["gantry_h"] + 1):
            p.put(u, fd, h, p.pal["gantry"])
        p.put(u, fd, D["gantry_h"] + 1, p.pal["gantry_top"])
    p.put(0, fd - 1, D["gantry_h"], p.pal["gantry"])            # a bracket out from the gantry, and a lamp hung under it
    p.put(0, fd - 1, D["gantry_h"] - 1, "minecraft:chain[axis=y]")
    p.put(0, fd - 1, D["gantry_h"] - 2, LANTERN_HANG)
    # the mast: a four-legged copper lattice behind the court, braced every few blocks, tapering, its top snapped and bent
    mc = (0, H + 1 + D["mast_off"])
    top = D["mast_h"]
    for h in range(1, top + 1):
        s = 2 if h <= D["taper"][0] else (1 if h <= D["taper"][1] else 0)
        legs = {(mc[0] + a * s, mc[1] + b * s) for a in (-1, 1) for b in (-1, 1)}
        if h > top - 4:
            continue
        for (u, d) in legs:
            p.put(u, d, h, p.mix("leg", u, d, h))
        if h in D["taper"]:                          # a landing where the lattice narrows: the legs above stand on it
            for a in range(-s, s + 1):
                for b in range(-s, s + 1):
                    p.blocks.setdefault((mc[0] + a, mc[1] + b, h), p.pal["brace"])
        if s and h % D["brace_every"] == 0:
            for a in range(-s, s + 1):
                for (u, d) in ((mc[0] + a, mc[1] - s), (mc[0] + a, mc[1] + s), (mc[0] - s, mc[1] + a), (mc[0] + s, mc[1] + a)):
                    p.blocks.setdefault((u, d, h), p.pal["brace"])
    # the snapped top: it leans out to one side a step at a time, each step face-joined to the last, chains hanging from its end
    for i in range(1, 5):
        u = mc[0] + i
        p.put(u, mc[1], top - 4 + i - 1, p.mix("leg", u, mc[1], top - 4 + i - 1))
        p.put(u, mc[1], top - 4 + i, p.mix("leg", u, mc[1], top - 4 + i))
    for h in range(top - 8, top - 1):
        p.put(mc[0] + 4, mc[1], h, "minecraft:chain[axis=y]")
    # the dish on the mast's front face, held off it by a short boom
    dc = (mc[0], mc[1] - 3)
    for a in range(-3, 4):
        for b in range(-3, 4):
            rr = math.hypot(a, b)
            if rr <= 3.2:
                u, h = dc[0] + a, D["dish_h"] + b
                p.put(u, dc[1], h, p.pal["dish_rim"] if rr > 2.2 else p.pal["dish"])
    p.put(dc[0], dc[1] - 1, D["dish_h"], p.pal["dish_core"])
    p.put(dc[0], dc[1] + 1, D["dish_h"], p.pal["leg"] if isinstance(p.pal["leg"], str) else p.pal["leg"][0][0])
    p.put(dc[0], dc[1] + 2, D["dish_h"], p.pal["brace"])
    for u in range(mc[0] - 3, mc[0] + 4):
        for d in range(mc[1] - 3, mc[1] + 3):
            p.extra.add((u, d))
            p.floor[(u, d)] = p.mix("floor", u, d, 0)
    # the transformer house: a small copper and deepslate block beside the court, its roof half fallen
    hx0, hd0 = H + 3, -3
    for u in range(hx0, hx0 + 5):
        for d in range(hd0, hd0 + 6):
            p.extra.add((u, d))
            edge = u in (hx0, hx0 + 4) or d in (hd0, hd0 + 5)
            for h in range(1, 5):
                if edge:
                    blk = p.pal["grate"] if (h in (2, 3) and (u + d) % 2 == 0) else p.mix("house", u, d, h)
                    p.put(u, d, h, blk)
                else:
                    p.put(u, d, h, AIR)
            if u + d < hx0 + hd0 + 7:                # the roof stands over half the house
                p.put(u, d, 5, "%s[type=bottom,waterlogged=false]" % p.pal["roof_slab"])
            p.floor[(u, d)] = p.mix("floor", u, d, 0)
    # a fallen spare mast on the ground on the other side, and scattered plates
    for d in range(-6, 7):
        u = -H - 4
        p.put(u, d, 1, p.mix("leg", u, d, 1) if d % 3 else p.pal["brace"])
        p.extra.add((u, d))
    for k in range(8):
        u = -H - 3 - int(p.r(12, k) * 4)
        d = -8 + int(p.r(13, k) * 16)
        p.put(u, d, 1, "%s[type=bottom,waterlogged=false]" % p.pal["plate_slab"])
        p.extra.add((u, d))
    # the forecourt
    f1 = fd - 1
    f0 = f1 - D["forecourt_len"] + 1
    for u in range(-D["forecourt_half"], D["forecourt_half"] + 1):
        for d in range(f0, f1 + 1):
            p.fore.add((u, d))
            p.floor[(u, d)] = p.mix("floor", u, d, 0)
    _clear(p, p.fore, 4)
    for u in (-D["forecourt_half"], D["forecourt_half"]):
        p.post(u, f1 - 1, p.pal["post"])
        p.post(u, f0 + 1, p.pal["post"])


# ---- S4: the tide shrine (Tapu Fini, Nihilego)

def tide_shrine(p):
    D = p.san["dims"]
    R = D["court_r"]
    I = {(u, d) for u in range(-R - 1, R + 2) for d in range(-R - 1, R + 2) if u * u + d * d < R * R}
    p.court |= I
    p.seal = ring_layers(I)
    W = dilate8(I, 2) - I
    p.wall |= W
    n = D["monoliths"]
    stones = []
    for k in range(n):
        t = 2 * math.pi * (k + 0.5) / n - math.pi / 2       # half a step off the front axis, so the gate stands between two
        stones.append((t, (R + 1.0) * math.cos(t), (R + 1.0) * math.sin(t)))
    tall = {}
    for k, (t, cu, cd) in enumerate(stones):
        back = (math.sin(t) + 1) / 2                        # 0 at the front, 1 at the back: taller behind
        h = D["stone_h"][0] + round(back * (D["stone_h"][1] - D["stone_h"][0])) + round(2 * p.r(14, k)) - 1
        if k in D["broken_stones"]:
            h = D["wall_h"] + 2 + round(2 * p.r(15, k))
        tall[k] = h
    for (u, d) in sorted(W):
        top = D["wall_h"] + (1 if p.r(16, u, d) < 0.25 else 0)
        for h in range(1, top + 1):
            p.put(u, d, h, p.mix("wall", u, d, h))
        p.put(u, d, top, p.mix("wall_cap", u, d, top))
    for k, (t, cu, cd) in enumerate(stones):
        cells = [(u, d) for (u, d) in W if math.hypot(u - cu, d - cd) <= 1.25]
        vein = k == D["nihilego_stone"]
        for (u, d) in cells:
            h_top = tall[k] - (1 if p.r(17, u, d) < 0.35 else 0)
            for h in range(1, h_top + 1):
                blk = p.mix("stone", u, d, h)
                if vein and h >= 3 and p.r(18, u, d, h) < 0.16:
                    blk = p.pal["ultra_vein"]
                p.put(u, d, h, blk)
            if vein and h_top >= 6:                          # a split top: one half gone, the other cracked through
                if (u + d) % 2 == 0:
                    for h in range(h_top - 2, h_top + 1):
                        p.put(u, d, h, AIR)
    # the gate: two posts and a double lintel over the door (a torii's shape), barrier in the outer ring
    door = [(u, d) for (u, d) in W if abs(u) <= 1 and d < 0]
    bar = min(d for _u, d in door)
    _door(p, door, bar, D["door_h"])
    gd = bar
    for u in (-D["gate_half"], D["gate_half"]):
        for h in range(1, D["gate_h"] + 1):
            p.put(u, gd, h, p.pal["gate_post"])
        p.extra.add((u, gd))
    for u in range(-D["gate_half"] - 1, D["gate_half"] + 2):
        p.put(u, gd, D["gate_h"] + 1, p.pal["lintel"])
        p.extra.add((u, gd))
    for u in range(-D["gate_half"] + 1, D["gate_half"]):
        p.put(u, gd, D["gate_h"] - 1, p.pal["tie"])
    for u in range(-D["gate_half"] + 1, D["gate_half"]):
        for h in range(D["door_h"] + 1, D["gate_h"] - 1):
            p.blocks.setdefault((u, gd, h), p.mix("wall", u, gd, h))
    # the court: a stone floor, the tide-pool ring (one deep), four causeways across it to the middle
    for (u, d) in I:
        r = math.hypot(u, d)
        p.floor[(u, d)] = p.mix("floor", u, d, 0)
        if D["pool_r"][0] <= r < D["pool_r"][1] and abs(u) > 0 and abs(d) > 0:
            p.floor[(u, d)] = WATER
            p.put(u, d, -1, p.pal["pool_bed"])
        elif abs(r - D["pool_r"][0] + 0.5) < 0.5 and (abs(u) == 0 or abs(d) == 0):
            p.floor[(u, d)] = p.pal["causeway"]
        elif r < 2.0:
            p.floor[(u, d)] = p.pal["heart"]
    _clear(p, I, 4)
    # low water bowls on stone stands inside the wall, a ring of them
    for k in range(6):
        t = 2 * math.pi * k / 6 + 0.3
        u, d = round((R - 2) * math.cos(t)), round((R - 2) * math.sin(t))
        if (u, d) in I and abs(u) > 1:
            p.put(u, d, 1, p.pal["bowl"])
    # the forecourt: a causeway path between two posts, shells of stone either side
    f1 = bar - 1
    f0 = f1 - D["forecourt_len"] + 1
    for u in range(-D["forecourt_half"], D["forecourt_half"] + 1):
        for d in range(f0, f1 + 1):
            p.fore.add((u, d))
            p.floor[(u, d)] = p.pal["causeway"] if abs(u) <= 1 else p.mix("floor", u, d, 0)
    _clear(p, p.fore - {(u, gd) for u in range(-9, 10)}, 4)
    for u in (-D["forecourt_half"], D["forecourt_half"]):
        p.post(u, f0 + 1, p.pal["post"])
        p.post(u, f1 - 2, p.pal["post"])


# ---- S5: the clock court (Dialga)

def clock_court(p):
    D = p.san["dims"]
    H, B = D["court_half"], D["court_back"]
    I = {(u, d) for u in range(-H, H + 1) for d in range(-H, B + 1)}
    p.court |= I
    p.seal = ring_layers(I)
    p.wall |= p.seal
    for (u, d) in sorted(p.seal):
        top = D["wall_h"] + round(1.2 * p.noise(20, 0.35 * (u + 3 * d)))
        if D["wall_fall"][0] <= u <= D["wall_fall"][1] and d < 0:
            top = D["wall_min"] + (1 if p.r(21, u) < 0.4 else 0)
        top = max(top, D["wall_min"])
        for h in range(1, top + 1):
            p.put(u, d, h, p.mix("wall_low" if h <= 2 else "wall", u, d, h))
        if (u + d) % 2 == 0 and top > D["wall_min"]:
            p.put(u, d, top + 1, p.mix("crest", u, d, top + 1))          # a merlon
    # rubble where the wall fell, outside it
    for k in range(14):
        u = D["wall_fall"][0] - 1 + int(p.r(22, k) * (D["wall_fall"][1] - D["wall_fall"][0] + 3))
        d = -H - 2 - int(p.r(23, k) * 2)
        p.put(u, d, 1, p.mix("rubble", u, d, 1))
        if p.r(24, k) < 0.5:
            p.put(u, d, 2, p.pal["rubble_slab"])
        p.extra.add((u, d))
    # the gatehouse: two squat towers with merlons either side of the door, an arch over it
    fd = -H - 1
    _door(p, [(u, fd) for u in (-1, 0, 1)], fd, D["door_h"])
    for side in (-1, 1):
        th = D["gate_tower_h"] - (2 if side > 0 else 0)
        for u in range(2 * side, 5 * side + side, side):
            for d in range(fd - 2, fd + 1):
                p.wall.add((u, d))
                for h in range(1, th + 1):
                    p.put(u, d, h, p.mix("wall", u, d, h))
                if (u + d) % 2 == 0:
                    p.put(u, d, th + 1, p.mix("crest", u, d, th + 1))
    for u in (-1, 0, 1):
        for h in range(D["door_h"] + 1, D["gate_tower_h"] - 1):
            p.put(u, fd, h, p.mix("wall", u, fd, h))
        p.put(u, fd, D["door_h"] + 1, p.pal["keystone"])
    # the tower: on the back wall, solid, a plinth, a long shaft with blind windows, the clock stage, a broken belfry
    tw = D["tower_half"]
    t0 = B + 1
    tc = (0, t0 + tw)
    TH = D["tower_h"]
    for u in range(-tw, tw + 1):
        for d in range(t0, t0 + 2 * tw + 1):
            p.wall.add((u, d))
            face = abs(u) == tw or d in (t0, t0 + 2 * tw)
            for h in range(1, TH - 5):
                if h <= 3:
                    blk = p.pal["plinth"]
                else:
                    blk = p.mix("tower", u, d, h)
                p.put(u, d, h, blk)
            # blind windows: tall recesses in each face's middle, two storeys
            mid = (abs(u) == tw and d == tc[1]) or (u == 0 and d in (t0, t0 + 2 * tw))
            if face and mid:
                for h in list(range(6, 10)) + list(range(13, 16)):
                    p.put(u, d, h, AIR)
                p.put(u, d, 10, p.pal["keystone"])
                p.put(u, d, 16, p.pal["keystone"])
    # the clock faces on all four sides: a disc of pale stone, two hands stopped at the same hour
    cy = D["clock_h"]
    for (fu, fd_, nu, nd) in ((0, t0, 1, 0), (0, t0 + 2 * tw, 1, 0), (-tw, tc[1], 0, 1), (tw, tc[1], 0, 1)):
        for a in range(-2, 3):
            for b in range(-2, 3):
                if a * a + b * b <= 5:
                    u, d = fu + a * nu, fd_ + a * nd
                    p.put(u, d, cy + b, p.pal["clock_face"])
        for b in (0, 1, 2):
            p.put(fu, fd_, cy + b, p.pal["clock_hand"])                    # the long hand at twelve
        p.put(fu + nu, fd_ + nd, cy - 1, p.pal["clock_hand"])                # the short hand, stopped toward five
        p.put(fu, fd_, cy, p.pal["clock_hub"])
    # the cornice and the belfry: corner piers, open arches, a roof half fallen, pinnacles one broken
    ch = TH - 5
    for u in range(-tw - 1, tw + 2):
        for d in range(t0 - 1, t0 + 2 * tw + 2):
            if abs(u) == tw + 1 or d in (t0 - 1, t0 + 2 * tw + 1):
                p.put(u, d, ch, "%s[facing=%s,half=top,shape=straight,waterlogged=false]" % (p.pal["cornice"], radial(u, d - tc[1])))
    for u in range(-tw, tw + 1):
        for d in range(t0, t0 + 2 * tw + 1):
            p.put(u, d, ch, p.pal["plinth"])
            corner = abs(u) >= tw - 1 and d in (t0, t0 + 1, t0 + 2 * tw - 1, t0 + 2 * tw)
            for h in range(ch + 1, TH):
                if corner:
                    p.put(u, d, h, p.mix("tower", u, d, h))
            if u + (d - t0) < 2 * tw - 1 or p.r(25, u, d) < 0.2:     # the roof stands over the half away from one corner
                p.put(u, d, TH, p.pal["roof"])
    for k, (su, sd) in enumerate(((-tw, t0), (tw, t0), (-tw, t0 + 2 * tw), (tw, t0 + 2 * tw))):
        ph = 3 if k != 3 else 1
        for h in range(TH, TH + 1 + ph):                  # from the pier's top up, whether the roof stands there or fell
            p.put(su, sd, h, p.pal["pinnacle"])
    # four stopped sundials and the floor's compass, the court floor worn and mossy
    for (u, d) in I:
        p.floor[(u, d)] = p.mix("floor", u, d, 0)
        if u == 0 or d == 0 or abs(u) == abs(d):
            if math.hypot(u, d) <= D["compass_r"]:
                p.floor[(u, d)] = p.pal["compass"]
    for (su, sd) in D["sundials"]:
        for a in range(-1, 2):
            for b in range(-1, 2):
                p.put(su + a, sd + b, 1, "%s[type=bottom,waterlogged=false]" % p.pal["dial_slab"])
        p.put(su, sd, 1, p.pal["dial_hub"])
        p.put(su, sd, 2, p.pal["gnomon"])
        p.put(su, sd, 3, p.pal["gnomon_tip"])
    _clear(p, I, 4)
    # the forecourt with lantern posts
    f1 = fd - 1
    f0 = f1 - D["forecourt_len"] + 1
    for u in range(-D["forecourt_half"], D["forecourt_half"] + 1):
        for d in range(f0, f1 + 1):
            if (u, d) in p.wall:
                continue
            p.fore.add((u, d))
            p.floor[(u, d)] = p.pal["path"] if abs(u) <= 1 else p.mix("floor", u, d, 0)
    _clear(p, p.fore, 4)
    for u in (-D["forecourt_half"], D["forecourt_half"]):
        p.post(u, f0 + 1, p.pal["post"])


# ---- S6: the sun arena (Koraidon)

def sun_arena(p):
    D = p.san["dims"]
    ru, rd = D["court_ru"], D["court_rd"]
    I = {(u, d) for u in range(-ru - 1, ru + 2) for d in range(-rd - 1, rd + 2) if (u / ru) ** 2 + (d / rd) ** 2 < 1.0}
    p.court |= I
    p.seal = ring_layers(I)
    W = dilate8(I, 2) - I
    p.wall |= W
    for (u, d) in sorted(W):
        t = math.atan2(d / rd, u / ru)
        top = D["wall_h"] + round(2.0 * p.noise(30, t))
        deg = math.degrees(t)
        for a, b in D["wall_falls"]:
            if a <= deg <= b:
                top = D["wall_min"] + (1 if p.r(31, u, d) < 0.35 else 0)
        top = max(top, D["wall_min"])
        outer = (u, d) not in p.seal
        for h in range(1, top + 1):
            if h == 1:
                blk = p.pal["footing"]
            elif h == D["band_h"]:
                blk = p.pal["band"]
            else:
                blk = p.mix("wall", u, d, h)
            p.put(u, d, h, blk)
        p.put(u, d, top, p.mix("crest", u, d, top))
        if outer and top >= 6 and round(deg) % 20 in range(0, 3):          # the blind arcade
            for h in (2, 3):
                p.put(u, d, h, AIR)
            p.put(u, d, 4, p.pal["keystone"])
    # the gate: obelisks either side of the door, a lintel of the sun's stone
    door = [(u, d) for (u, d) in W if abs(u) <= 1 and d < 0]
    bar = min(d for _u, d in door)
    _door(p, door, bar, D["door_h"])
    inner_d = max(d for _u, d in door)
    for u in (-1, 0, 1):
        for d in range(bar, inner_d + 1):
            p.put(u, d, D["door_h"] + 1, p.pal["lintel"])
    for side in (-1, 1):
        ou = side * D["obelisk_u"]
        od = bar - 1
        for a in (0, side):
            for b in (0, -1):
                u, d = ou + a, od + b
                p.extra.add((u, d))
                for h in range(1, D["obelisk_h"] - 2):
                    p.put(u, d, h, p.mix("obelisk", u, d, h))
        p.put(ou, od, D["obelisk_h"] - 2, p.pal["obelisk_top"])
        p.put(ou, od, D["obelisk_h"] - 1, p.pal["sun_cap"])
    # the arena floor: the sun's disc, its rays, scorched patches
    for (u, d) in I:
        r = math.hypot(u / ru * rd, d)
        a = (math.degrees(math.atan2(d, u)) + 360) % 45
        if r < 1.6:
            p.floor[(u, d)] = p.pal["sun_core"]
        elif r < 3.0:
            p.floor[(u, d)] = p.pal["sun_ring"]
        elif r < D["ray_r"] and (a < 5 or a > 40):
            p.floor[(u, d)] = p.pal["ray"]
        else:
            p.floor[(u, d)] = p.mix("floor", u, d, 0)
    _clear(p, I, 4)
    # cinder drifts against the outer wall on the falls' far side and the back: graded heaps the wall still stands over
    outer_ring = dilate8(I | W, D["drift_h"]) - (I | W)
    heap = {}
    for (u, d) in outer_ring:
        t = math.degrees(math.atan2(d / rd, u / ru))
        if any(a <= t <= b for a, b in D["drift_arcs"]):
            dist = min(max(abs(a - u), abs(b - d)) for (a, b) in W)
            hgt = D["drift_h"] + 1 - dist
            if hgt >= 1:
                heap[(u, d)] = hgt
    # a heap falls away a block a column on every side but the wall's: its arc's ends and its foot are graded too
    changed = True
    while changed:
        changed = False
        for c in list(heap):
            for du, dd in N4:
                n = (c[0] + du, c[1] + dd)
                if n in W or n in I:
                    continue
                lim = heap.get(n, 0) + 1
                if heap[c] > lim:
                    heap[c] = lim
                    changed = True
    for c, hgt in heap.items():
        if hgt >= 1:
            p.drift[c] = hgt
            p.extra.add(c)
    for k in range(7):                                               # half-buried columns in the drifts
        t = math.radians(D["drift_arcs"][k % len(D["drift_arcs"])][0] + p.r(32, k) * 40)
        u = round((ru + 5) * math.cos(t))
        d = round((rd + 5) * math.sin(t))
        h = 2 + int(p.r(33, k) * 4)
        for hh in range(1, h + 1):
            p.put(u, d, hh, p.mix("wall", u, d, hh))
        p.put(u, d, h, p.pal["keystone"])
        p.extra.add((u, d))
    # the forecourt
    f1 = bar - 1
    f0 = f1 - D["forecourt_len"] + 1
    for u in range(-D["forecourt_half"], D["forecourt_half"] + 1):
        for d in range(f0, f1 + 1):
            if (u, d) in p.extra and any(k[:2] == (u, d) for k in p.blocks):
                continue
            p.fore.add((u, d))
            p.floor[(u, d)] = p.pal["ray"] if abs(u) <= 1 else p.mix("floor", u, d, 0)
    _clear(p, {c for c in p.fore if not any((c[0], c[1], h) in p.blocks for h in (1, 2))}, 4)
    for u in (-D["forecourt_half"], D["forecourt_half"]):
        p.post(u, f0 + 1, p.pal["post"])


COMPOSERS = {"amphitheatre": amphitheatre, "relay": relay, "tide_shrine": tide_shrine, "clock_court": clock_court, "sun_arena": sun_arena}


_COMPOSED = {}


def compose(spec, san):
    """The piece in its local frame (cached by the record's own text and the seed: siting asks for it thousands of times)."""
    key = (spec["seed"], json.dumps({k: v for k, v in san.items() if k not in ("site",)}, sort_keys=True), json.dumps(spec["ground"], sort_keys=True))
    if key in _COMPOSED:
        return _COMPOSED[key]
    p = Piece(spec, san)
    if san["style"] not in COMPOSERS:
        raise SanctuaryError("%s: style %r is not one of %s" % (san["id"], san["style"], ", ".join(STYLES)))
    COMPOSERS[san["style"]](p)
    p.platform = dilate8(p.footprint(), spec["ground"]["apron"])
    band, ring = {}, set(p.platform)
    for k in range(1, spec["ground"]["band"] + 1):
        nxt = dilate8(ring, 1) - ring
        for c in nxt:
            band[c] = k
        ring |= nxt
    p.band = band
    _COMPOSED[key] = p
    return p


# ------------------------------------------------------------------ on the ground

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def band_tops(band, plat, xz, ground, yf):
    """{(u, d): surface y} of the graded band: each column's own ground, clamped into [lo, hi], where lo and hi are the lowest
    and highest a surface may stand and still be within one block a step (4-neighbours) of every edge it meets: the platform's
    floor on the inside, the untouched ground on the outside. Where the land itself is steeper than that (lo > hi) the column
    takes the middle. Pure arithmetic on the heightmap."""
    INF = 10 ** 6
    lo = {c: -INF for c in band}
    hi = {c: INF for c in band}
    for c in band:
        for du, dd in N4:
            n = (c[0] + du, c[1] + dd)
            if n in band:
                continue
            h = yf if n in plat else ground(*xz(*n))
            lo[c] = max(lo[c], h - 1)
            hi[c] = min(hi[c], h + 1)
    changed = True
    while changed:
        changed = False
        for c in band:
            for du, dd in N4:
                n = (c[0] + du, c[1] + dd)
                if n not in band:
                    continue
                if lo[n] - 1 > lo[c]:
                    lo[c] = lo[n] - 1
                    changed = True
                if hi[n] + 1 < hi[c]:
                    hi[c] = hi[n] + 1
                    changed = True
    out = {}
    for c in band:
        g = ground(*xz(*c))
        out[c] = min(max(g, lo[c]), hi[c]) if lo[c] <= hi[c] else (lo[c] + hi[c]) // 2
    return out


def geometry(spec, san, ground, centre=None, front=None):
    """Everything a sanctuary writes, on the heightmap: {"cells": {(x, y, z): block}, ...}. Every broken rule is a problem."""
    gr = spec["ground"]
    centre = tuple(centre or san["site"]["centre"])
    front = front or san["site"]["front"]
    xz = M.frame(centre, front)
    toks = dirs(front)
    p = compose(spec, san)
    plat = p.platform
    gs = sorted(ground(*xz(u, d)) for (u, d) in plat)
    yf = gs[(len(gs) - 1) // 2] + int(san.get("floor_offset", 0))
    probs, cells = [], {}
    # 1. the platform: cut down or built up to the floor, paved, the court's and forecourt's own floors
    cut = fill = 0
    for (u, d) in plat:
        x, z = xz(u, d)
        g = ground(x, z)
        if g - yf > gr["max_cut"]:
            probs.append("platform column (%d, %d): cut %d under the ground, over max_cut %d" % (x, z, g - yf, gr["max_cut"]))
        if yf - g > gr["max_fill"]:
            probs.append("platform column (%d, %d): built up %d, over max_fill %d" % (x, z, yf - g, gr["max_fill"]))
        for y in range(yf + 1, g + 1):
            cells[(x, y, z)] = AIR
            cut += 1
        for y in range(g + 1, yf):
            cells[(x, y, z)] = p.mix("foundation", u, d, y)
            fill += 1
        cells[(x, yf, z)] = resolve(p.floor.get((u, d)) or p.mix("apron", u, d, 0), toks)
    # 2. the graded band round it: the land runs from the platform's edge to the untouched ground, never steeper than a block a
    # column where the land allows it (band_tops: the ground clamped into the slope-limited envelope of both edges)
    band = p.band
    surf = band_tops(band, plat, xz, ground, yf)
    for (u, d), t in surf.items():
        x, z = xz(u, d)
        g = ground(x, z)
        if t > g:
            for y in range(g + 1, t):
                cells[(x, y, z)] = p.mix("grade_fill", u, d, y)
            cells[(x, t, z)] = p.mix("grade_top", u, d, t)
        elif t < g:
            for y in range(t + 1, g + 1):
                cells[(x, y, z)] = AIR
            cells[(x, t, z)] = p.mix("grade_top", u, d, t)
    # 3. drifts heaped on the platform (Sunscar's cinder): the surface rises by their height
    for (u, d), hgt in p.drift.items():
        x, z = xz(u, d)
        for h in range(1, hgt + 1):
            cells[(x, yf + h, z)] = p.mix("drift" if h < hgt else "drift_top", u, d, h)
    # 4. the piece itself (its air included: it opens the door, the recesses and the court)
    for (u, d, h), b in p.blocks.items():
        x, z = xz(u, d)
        cells[(x, yf + h, z)] = resolve(b, toks)
    # rules every piece keeps
    for (u, d) in p.seal:
        if (u, d) in {(a, b) for a, b, _h in p.door}:
            continue
        top = max([h for (a, b, h), blk in p.blocks.items() if (a, b) == (u, d) and blk != AIR and h >= 1] or [0])
        solid = [h for h in range(1, gr["wall_min"] + 1) if p.blocks.get((u, d, h), AIR) == AIR]
        if solid:
            probs.append("seal column (u=%d, d=%d): open at h %s, under wall_min %d (top %d)" % (u, d, solid, gr["wall_min"], top))
    if not p.barrier:
        probs.append("no barrier: the door has no closed row")
    door_cols = {(u, d) for u, d, _h in p.door}
    if not door_cols <= p.wall:
        probs.append("door cells outside the wall: %s" % sorted(door_cols - p.wall)[:4])
    if not p.fore:
        probs.append("no forecourt")
    # the zones the gate and keeper read
    def wbox(us, ds, ya, yb):
        pts = [xz(u, d) for u in (min(us), max(us)) for d in (min(ds), max(ds))]
        return [min(q[0] for q in pts), ya, min(q[1] for q in pts), max(q[0] for q in pts), yb, max(q[1] for q in pts)]
    cu = [u for u, _d in p.court]
    cd = [d for _u, d in p.court]
    hc = san["court"]["air_h"]
    out = {"cells": cells, "problems": probs, "yf": yf, "front": front, "centre_uv": list(centre), "piece": p,
           "platform": plat, "band": band, "band_top": surf, "cut": cut, "fill": fill}
    cx, cz = xz(0, 0)
    out["centre"] = [cx, yf, cz]
    out["chamber_zone"] = wbox(cu, cd, yf + 1, yf + hc)
    fu = [u for u, _d in p.fore]
    fdd = [d for _u, d in p.fore]
    out["ante_zone"] = wbox(fu, fdd, yf + 1, yf + 4)
    bu = [u for u, _d, _h in p.barrier]
    bd = [d for _u, d, _h in p.barrier]
    bh = [h for _u, _d, h in p.barrier]
    out["door_box"] = wbox(bu, bd, yf + min(bh), yf + max(bh))
    du = cu + [u for u, _d, _h in p.door]
    dd = cd + [d for _u, d, _h in p.door]
    out["inside_zone"] = wbox([min(du) - 1, max(du) + 1], [min(dd) - 1, max(dd) + 1], yf, yf + hc + 1)
    xs, ys, zs = zip(*cells)
    out["bounds"] = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]
    out["columns"] = sorted({(x, z) for x, _y, z in cells})
    out["height"] = max(h for (_u, _d, h), b in p.blocks.items() if b != AIR)
    out["ground"] = ground
    # the barrier and the rest of the door, in world cells
    out["barrier_cells"] = sorted((xz(u, d)[0], yf + h, xz(u, d)[1]) for u, d, h in p.barrier)
    out["door_cells"] = sorted((xz(u, d)[0], yf + h, xz(u, d)[1]) for u, d, h in p.door)
    return out


# ------------------------------------------------------------------ where a sanctuary may stand

def reach_of(spec, san):
    p = compose(spec, san)
    us = [u for u, _d in p.footprint()]
    ds = [d for _u, d in p.footprint()]
    return max(max(map(abs, us)), max(map(abs, ds))) + spec["ground"]["apron"] + spec["ground"]["band"] + 2


def check_box(spec, san):
    r = san["ring"]["max"] + reach_of(spec, san) + 8
    hx, hz = san["host_anchor"]
    return (hx - r, hz - r, hx + r, hz + r)


def authored_doc(spec):
    ids = {h["id"]: "a Habitat Block of this file, in its own sanctuary's court" for s in spec["sanctuaries"] for h in s.get("habitat") or []}
    files = dict(spec["authored_exempt"]["files"])
    return {"residents": [], "rules": {"authored_clearance_exempt": ids, "authored_clearance_exempt_files": files}}


def own_points(spec):
    """{(x, z)} of the single-column Habitat Block writes this file owns or owned: its own blocks (cobblers_habitats writes them)
    and the retired caves' old blocks, which a checkout's built cobblers_habitats may still hold until it is rebuilt."""
    pts = set()
    ids = {h["id"] for s in spec["sanctuaries"] for h in s.get("habitat") or []}
    for b in jload(HABITATS)["blocks"]:
        if b["id"] in ids:
            pts.add((b["position"]["x"], b["position"]["z"]))
    for rc in spec["retired_caves"]:
        for p in rc.get("habitat_points") or []:
            pts.add((p[0], p[2]))
    return pts


_PACK_BOXES = {}


def _memo_pack_boxes():
    """tools/mining_caves.py pack_boxes, read once per pack per process (each Clearance re-reads every built pack otherwise)."""
    if getattr(MC.pack_boxes, "_sanct_memo", False):
        return
    real = MC.pack_boxes

    def pack_boxes(pack_dir):
        k = str(Path(pack_dir).resolve())
        if k not in _PACK_BOXES:
            _PACK_BOXES[k] = real(pack_dir)
        return _PACK_BOXES[k]
    pack_boxes._sanct_memo = True
    MC.pack_boxes = pack_boxes


def clearance(spec, san, g0, inputs_root=None, need_packs=False, box=None):
    """tools/mining_caves.py Clearance over the sanctuary's checked box (or `box`). The other packs' writes skip this pack AND
    cobblers_caves: a full checkout's cobblers_caves still carries the retired K caves this tool restores and builds over (it is
    rebuilt without them); the natural caves it keeps are checked apart (natural_problems)."""
    _memo_pack_boxes()
    return MC.Clearance({"keep_clear": spec["keep_clear"]}, tuple(box) if box else check_box(spec, san), g0, inputs_root,
                        own_pack=_OwnPacks((PACK, "cobblers_caves")), need_packs=need_packs, own_file=SPEC,
                        authored_doc=authored_doc(spec), own_points=own_points(spec))


class _OwnPacks(str):
    """A pack name that compares unequal to every pack of the tuple (tools/mining_caves.py Clearance skips `p.name != own_pack`)."""

    def __new__(cls, names):
        s = str.__new__(cls, names[0])
        s.names = tuple(names)
        return s

    def __ne__(self, other):
        return other not in self.names

    def __eq__(self, other):
        return other in self.names

    __hash__ = str.__hash__


_STATIC = {}


def static_json(name):
    """A data file read once per process, for the siting's hot path (the files it reads are not written while it runs)."""
    if name not in _STATIC:
        _STATIC[name] = jload(ROOT / "data" / name)
    return _STATIC[name]


def natural_problems(spec, gm, min_gap=None):
    """Nothing of a sanctuary within natural_gap of a natural cave (data/caves.json mode natural): their mouths and chambers."""
    gap = min_gap or spec["keep_clear"]["natural_gap"]
    out = []
    try:
        caves = static_json("caves.json")["caves"]
    except (OSError, KeyError, ValueError) as exc:
        return ["cannot read data/caves.json for the natural caves: %s" % exc]
    x0, _y0, z0, x1, _y1, z1 = gm["bounds"]
    for c in caves:
        pts = [tuple(c["mouth"]["anchor"])] if c.get("mouth") else []
        if c.get("site"):
            pts.append((c["site"]["chamber_centre"][0], c["site"]["chamber_centre"][2]))
        for (px, pz) in pts:
            dx = max(x0 - px, 0, px - x1)
            dz = max(z0 - pz, 0, pz - z1)
            if math.hypot(dx, dz) < gap:
                out.append("%.0f from cave %s (%s), under natural_gap %d" % (math.hypot(dx, dz), c["id"], c.get("mode") or "kitted", gap))
    return out


def foreign_problems(spec, san, gm):
    """Spawn-free zones and natural Habitat Blocks' influence (tools/caves.py's rule, EXP-021)."""
    out = []
    m = spec["keep_clear"]["spawn_free_margin"]
    cols = gm["columns"]
    for z in static_json("spawn_suppression.json")["spawn_free_zones"]:
        x0, z0, x1, z1 = z["box"]
        hit = [c for c in cols if x0 - m <= c[0] <= x1 + m and z0 - m <= c[1] <= z1 + m]
        if hit:
            out.append("%d written column(s) within %d of the spawn-free zone %s, e.g. %s" % (len(hit), m, z["id"], hit[0]))
    mine = {h["id"] for s in spec["sanctuaries"] for h in s.get("habitat") or []}
    c = gm["centre"]
    for b in static_json("habitat_blocks.json")["blocks"]:
        if b["id"] in mine or b["style"] != "natural" or not b.get("replace_spawns"):
            continue
        bp = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
        for h in san.get("habitat") or []:
            d = math.dist(c, bp)
            if d < b["range_of_influence"] + san["court"]["reach"]:
                out.append("%s (reach %d) is %.1f from the natural block %s (range %d): their influence overlaps"
                           % (h["id"], san["court"]["reach"], d, b["id"], b["range_of_influence"]))
    return out


def site_problems(spec, san, gm, clear):
    probs = list(gm["problems"]) + foreign_problems(spec, san, gm) + natural_problems(spec, gm)
    hx, hz = san["host_anchor"]
    cx, _cy, cz = gm["centre"]
    dist = math.hypot(cx - hx, cz - hz)
    if not san["ring"]["min"] <= dist <= san["ring"]["max"]:
        probs.append("the centre is %.0f from its host anchor, outside the ring %s" % (dist, san["ring"]))
    bad = {}
    for c in gm["columns"]:
        w = clear.why(*c)
        if w:
            bad.setdefault(w, []).append(c)
        elif clear.tree(*c):
            bad.setdefault("within %d of a painted tree" % spec["keep_clear"]["tree_reach"], []).append(c)
    for w, cs in sorted(bad.items()):
        probs.append("%d written column(s) %s, e.g. %s" % (len(cs), w, cs[0]))
    return probs


def search(spec, san, g0, clear, top=8, step=3):
    """Candidate sites, best first: [(score, centre, front, yf, cut, fill)]. Score: the earthwork (cut + fill) over the platform's
    area, plus the distance from the host anchor / 40 (the old cave's place, unless a site nearby takes the land better), plus 4
    when the door faces away from `approach_from` (the town the old cave was a side trip of: the way in should face the way
    players come)."""
    hx, hz = san["host_anchor"]
    ax_, az_ = san.get("approach_from") or san["host_anchor"]
    x0, z0, x1, z1 = clear.box
    ground = M.BoxGround(g0, x0 - 8, z0 - 8, x1 + 8, z1 + 8)
    bad = (clear.code != 0) | clear.trees      # a painted tree's reach is a refusal too (site_problems), so it prefilters
    rmin, rmax = san["ring"]["min"], san["ring"]["max"]
    p0 = compose(spec, san)
    gr = spec["ground"]
    po = sorted(p0.platform)
    bo = sorted(p0.band)
    bk = np.array([p0.band[c] for c in bo])
    rot = {}
    for front in FRONTS:
        xz0 = M.frame((0, 0), front)
        w = np.array([xz0(int(u), int(d)) for u, d in po])
        v = np.array([xz0(int(u), int(d)) for u, d in bo])
        rot[front] = (w[:, 0], w[:, 1], v[:, 0], v[:, 1])
    ext = max(int(np.abs(np.concatenate([rot[f][2] for f in FRONTS])).max()), int(np.abs(np.concatenate([rot[f][3] for f in FRONTS])).max()))
    cands = []
    for cz in range(hz - rmax, hz + rmax + 1, step):
        for cx in range(hx - rmax, hx + rmax + 1, step):
            dist = math.hypot(cx - hx, cz - hz)
            if not rmin <= dist <= rmax:
                continue
            if cx - ext < x0 or cx + ext > x1 or cz - ext < z0 or cz + ext > z1:
                continue
            for front in FRONTS:
                wx, wz, vx, vz = rot[front]
                # the platform's ground under this placement, vectorised: the earthwork limits, then every column that would be
                # written (the platform, and the band where it changes the ground) clear of everything Clearance refuses
                gv = ground.arr[cz + wz - ground.z0, cx + wx - ground.x0]
                yf = int(np.sort(gv)[(len(gv) - 1) // 2])
                if int(gv.max()) - yf > gr["max_cut"] or yf - int(gv.min()) > gr["max_fill"]:
                    continue
                if bad[cz + wz - z0, cx + wx - x0].any():
                    continue
                gb = ground.arr[cz + vz - ground.z0, cx + vx - ground.x0]
                t = yf + np.round((gb - yf) * bk / (gr["band"] + 1)).astype(int)
                wr = t != gb
                if bad[(cz + vz - z0)[wr], (cx + vx - x0)[wr]].any():
                    continue
                xz = M.frame((cx, cz), front)
                ox, oz = xz(0, -1)
                away = (ox - cx) * (ax_ - cx) + (oz - cz) * (az_ - cz) < 0
                cands.append((float(np.abs(gv - yf).mean()) + dist / 40 + (4 if away else 0), (cx, cz), front))
    cands.sort()
    out = []
    for score, centre, front in cands[:4000]:
        gm = geometry(spec, san, ground, centre, front)
        if site_problems(spec, san, gm, clear):
            continue
        area = len(gm["platform"])
        xz = M.frame(centre, front)
        ox, oz = xz(0, -1)
        away = (ox - centre[0]) * (ax_ - centre[0]) + (oz - centre[1]) * (az_ - centre[1]) < 0
        s = round((gm["cut"] + gm["fill"]) / area + math.hypot(centre[0] - hx, centre[1] - hz) / 40 + (4 if away else 0), 2)
        out.append((s, list(centre), front, gm["yf"], gm["cut"], gm["fill"]))
        if top and len(out) >= top * 4:
            break
    out.sort(key=lambda o: (o[0], o[1], o[2]))
    return out[:top] if top else out


# ------------------------------------------------------------------ the retired caves and their restore

def retired_text(rc, ground):
    """The retired cave's build function exactly as tools/caves.py emitted it when it was applied, from its frozen record and spec:
    the restore and the audit both stand on it, and it must hash to applied_build_sha256 or nothing is restored (fail closed)."""
    import caves as CV
    spec = rc["frozen_spec"]
    cave = rc["cave"]
    gm = CV.geometry(spec, cave, ground)
    text = "\n".join(CV.build_lines(spec, {"cave": cave, "geometry": gm})) + "\n"
    got = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if got != rc["applied_build_sha256"]:
        raise SanctuaryError("%s: the retired cave's build text no longer hashes to its applied sha256 (%s, got %s): tools/caves.py's "
                             "geometry or emission moved, and the restore cannot know what it is undoing; nothing written"
                             % (rc["id"], rc["applied_build_sha256"][:16], got[:16]))
    return text, gm


def retired_cells(rc, ground):
    """{(x, y, z): role} of the retired cave, from tools/caves.py's geometry over the frozen record (hash-checked)."""
    _text, gm = retired_text(rc, ground)
    return gm


def retire_rects(cols):
    """{(x, z): key} -> [(x0, x1, z0, z1, key)]: runs of equal key along x, rows of equal runs merged over z (tools/legendaries.py)."""
    rows = {}
    for (x, z), k in sorted(cols.items(), key=lambda c: (c[0][1], c[0][0])):
        runs = rows.setdefault(z, [])
        if runs and runs[-1][1] == x - 1 and runs[-1][2] == k:
            runs[-1][1] = x
        else:
            runs.append([x, x, k])
    out, zs = [], sorted(rows)
    i = 0
    while i < len(zs):
        j = i
        while j + 1 < len(zs) and zs[j + 1] == zs[j] + 1 and rows[zs[j + 1]] == rows[zs[i]]:
            j += 1
        for x0, x1, k in rows[zs[i]]:
            out.append((x0, x1, zs[i], zs[j], k))
        i = j + 1
    return out


def _fills(x0, y0, z0, x1, y1, z1, block):
    """fill lines, split along z then x so none exceeds 32,768 blocks."""
    vol = (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1)
    if vol <= 32768:
        return ["fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, block)]
    if z1 > z0:
        m = (z0 + z1) // 2
        return _fills(x0, y0, z0, x1, y1, m, block) + _fills(x0, y0, m + 1, x1, y1, z1, block)
    m = (x0 + x1) // 2
    return _fills(x0, y0, z0, m, y1, z1, block) + _fills(m + 1, y0, z0, x1, y1, z1, block)


def terrain_lines(cols, ground, terrain):
    """Every column of `cols` ({(x, z): (lo, hi)}) back to terrain over its y range: `deep` to three under the ground, `under`
    to one under, `surface` at the ground, air above, up to hi (tools/legendaries.py terrain_lines' rule)."""
    keyed = {c: (ground(c[0], c[1]), lo, hi) for c, (lo, hi) in cols.items()}
    out = []
    for x0, x1, z0, z1, (gy, lo, hi) in retire_rects(keyed):
        def band(a, b, block):
            if a <= b:
                out.extend(_fills(x0, a, z0, x1, b, z1, block))
        band(lo, min(gy - 3, hi), terrain["deep"])
        band(max(lo, gy - 2), min(gy - 1, hi), terrain["under"])
        band(max(lo, gy), min(gy, hi), terrain["surface"])
        band(max(lo, gy + 1), hi, AIR)
    return out


def restore_columns(gm):
    """{(x, z): (lo, hi)} over every cell the retired cave wrote."""
    cols = {}
    for (x, y, z) in gm["cells"]:
        lo, hi = cols.get((x, z), (y, y))
        cols[(x, z)] = (min(lo, y), max(hi, y))
    return cols


def restore_probes(rc, gm):
    """[(x, y, z, block)]: cells that stand only while the retired cave does (the chamber floor beside its middle, the mouth's
    beam, the closed door's barrier); the restore runs while ANY shows, and the sanctuary's build refuses while any shows."""
    import caves as CV
    cave = rc["cave"]
    cells = gm["cells"]
    front = gm["front"]
    out = []
    c = (gm["centre"][0] + 1, gm["yh"], gm["centre"][2])
    if cells.get(c) != "floor":
        raise SanctuaryError("%s: the chamber probe %s is %r, not the floor" % (rc["id"], c, cells.get(c)))
    out.append(c + (base(CV.block_of(cave, "floor", front)),))
    beam = next((k for k, r in sorted(cells.items()) if r == "beam"), None)
    if beam:
        out.append(beam + (base(CV.block_of(cave, "beam", front)),))
    bar = next((k for k, r in sorted(cells.items()) if r == "barrier"), None)
    if bar:
        out.append(bar + (BARRIER,))
    return out


def void_boxes(gm):
    """[(x0, y0, z0, x1, y1, z1)]: the retired cave's open cells (air, its lantern posts and door), as per-column runs merged."""
    cols = {}
    for (x, y, z), r in gm["cells"].items():
        if r in ("air", "fence", "lantern", "hanglantern", "barrier", "crystal", "knob"):
            lo, hi = cols.get((x, z), (y, y))
            cols[(x, z)] = (min(lo, y), max(hi, y))
    return [(x0, lo, z0, x1, hi + 1, z1) for x0, x1, z0, z1, (lo, hi) in retire_rects(cols)]


def restore_parts(rc):
    """(entry function, the act's function, score holder) of one retired cave's restore."""
    b = "%s/restore/%s" % (F, rc["id"])
    return b, b + "_do", "sanct_restore_%s" % rc["cave"]["kind"].lower()


def restore_files(spec, rc, ground):
    """{function name (under sanctuaries/): lines} of one retired cave's restore: the entry counts the players standing in its
    voids into #<holder> cobblers_chunk_look (tools/reapply.py's chunk_look check reads 0 or the step fails), and only with none
    and while a probe shows the cave runs the act: every column back to terrain, the probes last."""
    gm = retired_cells(rc, ground)
    entry, act, holder = restore_parts(rc)
    probes = restore_probes(rc, gm)
    sel = []
    for (x0, y0, z0, x1, y1, z1) in void_boxes(gm):
        sel.append("tag @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] add %s" % (x0, y0, z0, x1 - x0, y1 - y0, z1 - z0, HELD))
    head = ["# Generated by tools/sanctuaries.py from data/sanctuaries.json: the retired cave %s (%s, %s), retired %s."
            % (rc["cave"]["name"], rc["id"], rc["cave"]["kind"], rc["retired"]),
            "# chunks-loaded-by: tools/reapply.py's sanctuary step (forceload add over the old cave and the sanctuary before this runs)",
            "# A player standing in one of the cave's voids is held, counted into #%s %s (the step reads 0 back, so a refusal" % (holder, CHUNK_OBJ),
            "# stops the run), and nothing is written while anyone is. The act runs only while a probe still shows the cave, so a",
            "# second run writes nothing.",
            "scoreboard objectives add %s dummy" % CHUNK_OBJ,
            "tag @a remove %s" % HELD] + sel + [
            "execute store result score #%s %s if entity @a[tag=%s]" % (holder, CHUNK_OBJ, HELD)]
    for (x, y, z, blk) in probes:
        head.append("execute if score #%s %s matches 0 if block %d %d %d %s run function %s" % (holder, CHUNK_OBJ, x, y, z, blk, act))
    t = rc["terrain"]
    body = ["# Generated by tools/sanctuaries.py: %s's every written column back to the heightmap's terrain (%s at the ground, "
            "%s under it, %s below; air above)" % (rc["id"], t["surface"], t["under"], t["deep"]),
            "# chunks-loaded-by: %s (its caller holds the old cave's whole box)" % entry]
    cols = restore_columns(gm)
    pk = {(x, z) for (x, _y, z, _b) in probes}
    body += terrain_lines({c: v for c, v in cols.items() if c not in pk}, ground, t)
    body.append("# the probes' columns last: a run that stopped half way is run again")
    body += terrain_lines({c: v for c, v in cols.items() if c in pk}, ground, t)
    name_e = entry[len(F) + 1:]
    name_a = act[len(F) + 1:]
    return {name_e: head, name_a: body}


# ------------------------------------------------------------------ levels and gates (tools/caves.py's readers)

def flag_caps():
    t = jload(LEGENDARIES)["level_caps"]["upper_bound_by_badges"]
    caps = {"champion_cleared": int(t["champion"])}
    for n in range(1, 9):
        caps["gym%d_cleared" % n] = int(t[str(n)])
    return caps


def progression_flags():
    return {f["id"] for f in jload(PROGRESSION)["flags"]}


def band_of(x, z):
    import subregion_boxes as SB
    regs = jload(REGIONS)["subregions"]
    bands = {s["id"]: s for s in jload(SPAWNS)["subregions"]}
    for r in regs:
        if any(SB.point_in_polygon(x, z, poly) for poly in r["polygons"]) and r["id"] in bands:
            b = bands[r["id"]]["level_band"]
            return r["id"], int(b["minimum"]), int(b["maximum"]), b.get("tier")
    return None, None, None, None


def level_range(entry):
    lv = str(entry["level"])
    if "-" in lv:
        a, b = lv.split("-")
        return int(a), int(b)
    return int(lv), int(lv)


def static_problems(spec):
    out = []
    seen = set()
    try:
        flags, caps = progression_flags(), flag_caps()
    except (OSError, KeyError, ValueError) as exc:
        return ["cannot read the progression flags or the level caps: %s" % exc]
    for s in spec["sanctuaries"]:
        sid = s["id"]
        if sid in seen:
            out.append("%s: a duplicate id" % sid)
        seen.add(sid)
        if s["style"] not in STYLES:
            out.append("%s: style %r" % (sid, s["style"]))
        g = s.get("gate") or {}
        if g.get("kind") != "partition" or not g.get("flags"):
            out.append("%s: a sanctuary's gate is a partition with flags" % sid)
        for f in g.get("flags") or []:
            if f not in flags:
                out.append("%s: gate flag %s is not declared in data/progression.json" % (sid, f))
        occ = s["occupant"]
        if occ["mode"] not in MODES:
            out.append("%s: occupant mode %r (a sanctuary hosts a legendary: rare_spawn or area_boss)" % (sid, occ["mode"]))
        if occ["mode"] == "area_boss":
            if "champion_cleared" not in (g.get("flags") or []):
                out.append("%s: an area boss is a native alpha, catchable only after the Champion; its gate must hold champion_cleared" % sid)
            if "alpha=true" not in occ["properties"]:
                out.append("%s: a boss is a native alpha (alpha=true)" % sid)
            k = occ["keeper"]
            if k["cooldown_faint_ticks"] != 24000 or k["cooldown_catch_ticks"] != 72000:
                out.append("%s: the respawn rule is 24,000 ticks after a faint and 72,000 after a catch (the owner, 2026-10-12)" % sid)
            if occ["guardian_tag"] != "cobblers.guardian":
                out.append("%s: guardian_tag must be cobblers.guardian (the blackout's)" % sid)
            if k["spawn_clear"] >= k["spawn_radius"] or k["trigger_radius"] >= k["settle_radius"]:
                out.append("%s: keeper radii out of order" % sid)
            if s.get("habitat"):
                out.append("%s: a boss sanctuary has no Habitat Block (the owner: 'we don't need the non-legendaries')" % sid)
            if occ.get("co_occupants"):
                out.append("%s: co_occupants are for a rare-spawn court only" % sid)
        if occ["mode"] == "rare_spawn":
            hs = s.get("habitat") or []
            if len(hs) != 1 or hs[0]["part"] != "court":
                out.append("%s: a rare-spawn sanctuary has one Habitat Block, in its court" % sid)
            ents = [e for h in hs for e in h["pool"]["entries"]]
            for sp in [occ["species"]] + list(occ.get("co_occupants") or []):
                m = [e for e in ents if species_id(e["species"]) == sp]
                if len(m) != 1 or m[0]["bucket"] != "ultra-rare":
                    out.append("%s: %s must be one ultra-rare entry of the court's pool" % (sid, sp))
            cap = min(caps[f] for f in g.get("flags") or [] if f in caps) if any(f in caps for f in g.get("flags") or []) else None
            for e in ents:
                if e["bucket"] not in ("common", "uncommon", "rare", "ultra-rare"):
                    out.append("%s: entry %s bucket %r" % (sid, e["species"], e["bucket"]))
                if e["level"] == "band":
                    out.append("%s: entry %s: a court's levels are set by its gate, not a band" % (sid, e["species"]))
                    continue
                if cap is not None and level_range(e)[1] > cap:
                    out.append("%s: entry %s level %s is over the gate's cap %d" % (sid, e["species"], e["level"], cap))
        for k in ("foundation", "apron", "grade_top", "grade_fill"):
            if k not in s["palette"]:
                out.append("%s: palette lacks %s" % (sid, k))
    for rc in spec["retired_caves"]:
        for k in ("id", "retired", "why", "applied_build_sha256", "frozen_spec", "cave", "terrain"):
            if k not in rc:
                out.append("retired cave %s: lacks %s" % (rc.get("id"), k))
        if rc.get("successor") and rc["successor"] not in seen:
            out.append("retired cave %s: successor %s is not a sanctuary" % (rc["id"], rc["successor"]))
    return out


# ------------------------------------------------------------------ the model

def model(spec=None, source_root=None, inputs_root=None, need_packs=False, clear_check=True):
    spec = spec or load()
    g0 = G.Ground(source_root)
    probs = static_problems(spec)
    notes, plan = [], []
    for san in spec["sanctuaries"]:
        if not san.get("site"):
            probs.append("%s: no site (python tools/sanctuaries.py author)" % san["id"])
            continue
        gm = geometry(spec, san, g0)
        if clear_check:
            b = gm["bounds"]
            clear = clearance(spec, san, g0, inputs_root, need_packs=need_packs, box=(b[0] - 2, b[2] - 2, b[3] + 2, b[5] + 2))
            notes += ["%s: %s" % (san["id"], n) for n in clear.notes]
            probs += ["%s: %s" % (san["id"], p) for p in site_problems(spec, san, gm, clear)]
        else:
            probs += ["%s: %s" % (san["id"], p) for p in gm["problems"]]
        plan.append({"san": san, "geometry": gm})
    retired = []
    for rc in spec["retired_caves"]:
        try:
            retired.append({"rc": rc, "geometry": retired_cells(rc, g0)})
        except SanctuaryError as exc:
            probs.append(str(exc))
    # a sanctuary must never lay, at a retired cave's probe, the very block the probe looks for: a re-run would take the cave for
    # standing and restore it over the sanctuary (then build it again: harmless, but a lie in the step's report)
    built = {}
    for e in plan:
        built.update(e["geometry"]["cells"])
    for r in retired:
        for (x, y, z, blk) in restore_probes(r["rc"], r["geometry"]):
            if base(built.get((x, y, z), "")) == blk:
                probs.append("%s: a sanctuary writes %s at the retired cave's probe (%d, %d, %d)" % (r["rc"]["id"], blk, x, y, z))
    return plan, retired, probs, notes


# ------------------------------------------------------------------ the pack

def build_name(san):
    return "build_%s" % san["id"]


def build_lines(spec, entry, retired):
    """The set piece, one final block a cell. It refuses (returns) while any probe of a retired cave it is built over still shows,
    so it is never laid over a cave whose restore was refused."""
    san, gm = entry["san"], entry["geometry"]
    lines = ["# Generated by tools/sanctuaries.py from data/sanctuaries.json: %s (%s, %s, style %s)" % (san["name"], san["id"], san["kind"], san["style"]),
             "# chunks-loaded-by: tools/reapply.py's sanctuary step (forceload add over the old cave and the sanctuary before this runs)"]
    for r in retired:
        if r["rc"].get("successor") == san["id"]:
            for (x, y, z, blk) in restore_probes(r["rc"], r["geometry"]):
                lines.append("execute if block %d %d %d %s run return 0" % (x, y, z, blk))
    lines += M.column_runs(gm["cells"])
    lines.append("scoreboard players set #%s_open %s 0" % (san["id"], spec["gate"]["objective"]))
    return lines


def box_args(b):
    return "%d %d %d %d %d %d" % tuple(b)


def sel_box(b):
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (b[0], b[1], b[2], b[3] - b[0], b[4] - b[1], b[5] - b[2])


def flag_sel(spec, flags):
    return "advancements={%s}" % ",".join("%s:flag/%s=true" % (spec["flag_namespace"], f) for f in flags)


def grow(b, n):
    return [b[0] - n, b[1] - n, b[2] - n, b[3] + n, b[4] + n, b[5] + n]


def nbt(d):
    return "{%s}" % ",".join("%s:%s" % kv for kv in d.items())


def gate_files(spec, entry):
    """tools/caves.py gate_files, moved: near / open / close."""
    san, gm = entry["san"], entry["geometry"]
    sid, obj = san["id"], spec["gate"]["objective"]
    g = "gate/%s" % sid
    gf = "%s/%s" % (F, g)
    fl = flag_sel(spec, san["gate"]["flags"])
    ante, door, inside = gm["ante_zone"], gm["door_box"], gm["inside_zone"]
    fn = {}
    fn["%s/near" % g] = [
        "# %s. The gate is the advancement predicate on the line that opens it (tools/legendaries.py's near)." % san["name"],
        "execute if entity @a[%s,%s] unless score #%s_open %s matches 1 run function %s/open" % (sel_box(ante), fl, sid, obj, gf),
        "# never shut anyone in: closed only when no flagged player is in the forecourt and nobody is in the door or the court",
        "execute unless entity @a[%s,%s] unless entity @a[%s,gamemode=!spectator] if score #%s_open %s matches 1 run function %s/close"
        % (sel_box(ante), fl, sel_box(inside), sid, obj, gf)]
    fn["%s/open" % g] = [
        "# chunks-loaded-by: the player who trips it. %s/near only calls this while a flagged player stands in the forecourt" % gf,
        "scoreboard players set #%s_open %s 1" % (sid, obj),
        "fill %s %s replace %s" % (box_args(door), AIR, spec["gate"]["door_block"]),
        "playsound minecraft:block.beacon.activate master @a[%s] %d %d %d 1 0.6" % (sel_box(grow(inside, 6)), gm["centre"][0], gm["centre"][1], gm["centre"][2]),
        "tellraw @a[%s] %s" % (sel_box(grow(ante, 3)), json.dumps({"text": "The way opens.", "color": "aqua", "italic": True}))]
    fn["%s/close" % g] = [
        "# chunks-loaded-by: the player who trips it: near only runs while somebody is within %d blocks" % spec["gate"]["reach"],
        "scoreboard players set #%s_open %s 0" % (sid, obj),
        "fill %s %s replace %s" % (box_args(door), spec["gate"]["door_block"], AIR)]
    return fn


def boss_files(spec, entry):
    """tools/caves.py boss_files, moved: the keeper of an area boss (tools/drowned_quarry.py keeper_files' shape), its clock set by
    how the last one ended and a spawn only for a player holding the gate flag. NEVER a blackout guardian (C25)."""
    san, gm = entry["san"], entry["geometry"]
    occ = san["occupant"]
    k = occ["keeper"]
    sid, obj = san["id"], spec["gate"]["objective"]
    T, D, Gd = occ["tag"], occ["dormant_tag"], occ["guardian_tag"]
    cx, cy, cz = gm["centre"]
    sy = cy + 1
    spot = (cx + 0.5, sy, cz + 0.5)
    sx = "x=%.1f,y=%d,z=%.1f" % spot
    at = "%.1f %d %.1f" % spot
    P = "%s/boss/%s" % (F, sid)
    fl = flag_sel(spec, san["gate"]["flags"])
    sp = 'nbt={Pokemon:{Species:"cobblemon:%s"}}' % occ["species"]
    chz = gm["chamber_zone"]
    yaw = YAW[gm["front"]]
    n, ab, gone, resp, caught = ["#%s_%s" % (sid, s) for s in ("n", "abs", "gone", "resp", "caught")]
    mon = json.dumps({"text": occ["message"], "color": "gold", "italic": True}, ensure_ascii=False)
    fn = {}
    fn["boss/%s/load" % sid] = [
        "# the clock is set here only when it was never set: a restart never moves it",
        "execute unless score %s %s matches -2147483648.. run scoreboard players set %s %s %d" % (gone, obj, gone, obj, NEVER),
        "schedule function %s/keeper %dt replace" % (P, k["period_ticks"])]
    fn["boss/%s/keeper" % sid] = [
        "# the keeper's loop: only while the court's chunk is loaded (nobody has to be near for the return clock)",
        "execute store result score #now %s run time query gametime" % obj,
        "execute if loaded %d %d %d run function %s/keep" % (cx, cy, cz, P),
        "schedule function %s/keeper %dt replace" % (P, k["period_ticks"])]
    fn["boss/%s/keep" % sid] = [
        "# Present: ours by tag (a guardian keeps our tag), or a guardian the blackout REBUILT, which does not, found by its tag",
        "# and species near the spot. Never a bare distance, and never a guardian killed, held, woken or settled.",
        "execute store result score %s %s if entity @e[type=cobblemon:pokemon,tag=%s]" % (n, obj, T),
        "execute if score %s %s matches 0 if entity @e[type=cobblemon:pokemon,tag=%s,%s,distance=..%d,%s] run scoreboard players set %s %s 1"
        % (n, obj, Gd, sx, k["guardian_search_radius"], sp, n, obj),
        "# a duplicate (a spawn that raced a slow entity load): the furthest one goes, and NEVER a guardian",
        "execute if score %s %s matches 2.. run kill @e[type=cobblemon:pokemon,tag=%s,tag=!%s,%s,limit=1,sort=furthest]" % (n, obj, T, Gd, sx),
        "execute if score %s %s matches 1.. run scoreboard players set %s %s 0" % (n, obj, ab, obj),
        "execute if score %s %s matches 1.. run scoreboard players set %s %s %d" % (n, obj, gone, obj, PRESENT),
        "# a catch flag left by a Pokemon of this species caught while the boss lives (a released one recaught) is stale",
        "execute if score %s %s matches 1.. run scoreboard players set %s %s 0" % (n, obj, caught, obj),
        "execute if score %s %s matches 1.. as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run function %s/hold" % (n, obj, T, Gd, P),
        "execute if score %s %s matches 1.. run return 0" % (n, obj),
        "# absent on %d loaded passes in a row (entities load a moment after their chunk) before it counts as gone" % k["absent_passes"],
        "scoreboard players add %s %s 1" % (ab, obj),
        "execute if score %s %s matches ..%d run return 0" % (ab, obj, k["absent_passes"] - 1),
        "# first seen gone (fainted or caught): the length of the clock is chosen by how it ended (72,000 after a catch, 24,000 after",
        "# a faint), then the clock starts now. Only these lines move it, and only from the 'seen present' value",
        "execute if score %s %s matches %d run scoreboard players set %s %s %d" % (gone, obj, PRESENT, resp, obj, k["cooldown_faint_ticks"]),
        "execute if score %s %s matches %d if score %s %s matches 1 run scoreboard players set %s %s %d"
        % (gone, obj, PRESENT, caught, obj, resp, obj, k["cooldown_catch_ticks"]),
        "execute if score %s %s matches %d run scoreboard players operation %s %s = #now %s" % (gone, obj, PRESENT, gone, obj, obj),
        "scoreboard players set %s %s 0" % (caught, obj),
        "# the clock must have run; a boss never yet brought in (the 'never' value) has no clock",
        "scoreboard players operation #d %s = #now %s" % (obj, obj),
        "scoreboard players operation #d %s -= %s %s" % (obj, gone, obj),
        "execute if score %s %s matches %d run scoreboard players set #d %s 2000000000" % (gone, obj, NEVER, obj),
        "execute if score #d %s < %s %s run return 0" % (obj, resp, obj),
        "# never conjured in front of anyone, and only for a player holding the gate flag to meet it",
        "execute if entity @a[%s,distance=..%d] run return 0" % (sx, k["spawn_clear"]),
        "execute unless entity @a[%s,distance=..%d,gamemode=!spectator,%s] run return 0" % (sx, k["spawn_radius"], fl),
        "function %s/spawn" % P]
    fn["boss/%s/hold" % sid] = [
        "# as the Pokemon (never a guardian). DORMANT: held on its spot, facing the door; it wakes for a player in the court.",
        "execute if entity @s[tag=%s] unless entity @s[%s,distance=..%s] run tp @s %s %d 0" % (D, sx, k["home_tolerance"], at, yaw),
        "execute if entity @s[tag=%s] if entity @a[%s,gamemode=!spectator] run function %s/wake" % (D, sel_box(chz), P),
        "# AWAKE: it lies down again on its spot when nobody is within %d (a fight fled is not won)" % k["settle_radius"],
        "execute if entity @s[tag=!%s] unless entity @a[%s,distance=..%d,gamemode=!spectator] run function %s/settle" % (D, sx, k["settle_radius"], P)]
    fn["boss/%s/wake" % sid] = [
        "# as the Pokemon: the trigger, a STATE CHECK on the keeper's own loop, never an advancement (CELEBI_WAKE.md 1)",
        "tag @s remove %s" % D,
        "data merge entity @s %s" % nbt(occ["awake_nbt"]),
        "tellraw @a[%s,distance=..48] %s" % (sx, mon),
        "playsound %s hostile @a[%s,distance=..48] %s 2 0.6" % (occ["sound"], sx, at)]
    fn["boss/%s/settle" % sid] = [
        "# as the Pokemon: everyone has gone, so it goes back to its spot and sleeps",
        "tp @s %s %d 0" % (at, yaw),
        "data merge entity @s %s" % nbt(occ["dormant_nbt"]),
        "tag @s add %s" % D]
    props = " ".join(["level=%d" % occ["level"]] + list(occ["properties"]))
    fn["boss/%s/spawn_at" % sid] = ["$spawnpokemonat $(x) $(y) $(z) %s %s" % (occ["species"], props)]
    fn["boss/%s/spawn" % sid] = [
        "# a wild one through the macro (EXP-046), then bound at once",
        "function %s/spawn_at {x:\"%.1f\",y:%d,z:\"%.1f\"}" % (P, spot[0], sy, spot[2]),
        "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..3,%s,limit=1,sort=nearest] run function %s/bind" % (at, T, sp, P)]
    fn["boss/%s/bind" % sid] = [
        "# as the new Pokemon: tagged, kept from the despawner (PersistenceRequired, EXP-041), dormant on its spot",
        "tag @s add %s" % T, "tag @s add %s" % D,
        "data merge entity @s %s" % nbt(occ["dormant_nbt"]),
        "tp @s %s %d 0" % (at, yaw),
        "scoreboard players set %s %s %d" % (gone, obj, PRESENT),
        "scoreboard players set %s %s 0" % (ab, obj),
        "scoreboard players set %s %s 0" % (caught, obj)]
    fn["boss/%s/caught" % sid] = [
        "# as the catcher of a %s within %d of the spot (the pokemon_captured callback): the keeper reads this at its next pass" % (occ["species"], k["catch_radius"]),
        "scoreboard players set %s %s 1" % (caught, obj)]
    return fn


def callbacks(spec, plan):
    lines = ["'Generated by tools/sanctuaries.py from data/sanctuaries.json. A boss species caught near its sanctuary tells the keeper,';",
             "'which then waits the long clock. Anywhere else it does nothing.';", "t.id = q.pokemon.species.identifier;"]
    n = 0
    for e in plan:
        occ = e["san"]["occupant"]
        if occ["mode"] != "area_boss":
            continue
        cx, cy, cz = e["geometry"]["centre"]
        k = occ["keeper"]
        cmd = ("execute as ' + q.player.uuid + ' at @s if entity @s[x=%d,y=%d,z=%d,distance=..%d] run function %s/boss/%s/caught"
               % (cx, cy + 1, cz, k["catch_radius"], F, e["san"]["id"]))
        lines += ["t.id == 'cobblemon:%s' ? {" % occ["species"], "  q.run_command('%s');" % cmd, "};"]
        n += 1
    return {"data/cobblemon/callbacks/pokemon_captured/cobblers_sanctuaries.molang": "\n".join(lines) + "\n"} if n else {}


def pack_files(spec, plan, retired, ground):
    files = {"pack.mcmeta": json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: the legendary sanctuaries (tools/sanctuaries.py, data/sanctuaries.json)"}}, indent=2) + "\n"}
    obj = spec["gate"]["objective"]
    load_ = ["# the sanctuaries' driver state (tools/sanctuaries.py): scores live in the world's scoreboard, so a restart repeats nothing",
             "scoreboard objectives add %s dummy" % obj]
    tick = ["# every %d ticks: each gate's driver, only while a player is within %d of its court" % (spec["gate"]["period_ticks"], spec["gate"]["reach"])]
    fns = {}
    for r in retired:
        fns.update(restore_files(spec, r["rc"], ground))
    for e in plan:
        san, gm = e["san"], e["geometry"]
        fns[build_name(san)] = build_lines(spec, e, retired)
        cx, cy, cz = gm["centre"]
        load_.append("execute unless score #%s_open %s matches -2147483648.. run scoreboard players set #%s_open %s 0" % (san["id"], obj, san["id"], obj))
        tick.append("execute positioned %d %d %d if entity @a[distance=..%d] run function %s/gate/%s/near" % (cx, cy, cz, spec["gate"]["reach"], F, san["id"]))
        fns.update(gate_files(spec, e))
        if san["occupant"]["mode"] == "area_boss":
            fns.update(boss_files(spec, e))
            load_.append("function %s/boss/%s/load" % (F, san["id"]))
    load_.append("schedule function %s/tick %dt replace" % (F, spec["gate"]["period_ticks"]))
    tick.append("schedule function %s/tick %dt replace" % (F, spec["gate"]["period_ticks"]))
    fns["load"], fns["tick"] = load_, tick
    for name, body in fns.items():
        bad = FL.check_lines(body, name)
        if bad:
            raise SanctuaryError("function %s would be refused: %s" % (name, bad[:3]))
        files["data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, name)] = "\n".join(body) + "\n"
    files["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s/load" % F]}, indent=2) + "\n"
    files.update(callbacks(spec, plan))
    return files


def write(files, out=None):
    out = Path(out or OUT)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return {Path(r).stem: t.count("\n") for r, t in files.items() if r.endswith(".mcfunction")}


# ------------------------------------------------------------------ the steps tools/reapply.py runs

def _union_box(*bounds):
    x0 = min(b[0] for b in bounds) - 2
    z0 = min(b[2] for b in bounds) - 2
    x1 = max(b[3] for b in bounds) + 2
    z1 = max(b[5] for b in bounds) + 2
    return (x0, z0, x1, z1)


def placement_steps(spec=None, g=None):
    """For tools/reapply.py, the sanctuary step, AFTER R9CK and BEFORE R9E: per retired cave, hold its box (and its successor's),
    restore it and read back that nobody was held (a refusal fails the step), then build the successor; a retired cave with no
    successor (K1) is restored alone. The boxes come from the heightmap alone, so listing the steps needs no derived/ or build/.
    The read-back is tools/reapply.py's ("check", ("chunk_look", holder, 0, label)): it reads #<holder> cobblers_chunk_look."""
    spec = spec or load()
    g = g or G.Ground()
    sans = {s["id"]: s for s in spec["sanctuaries"]}
    out = []
    done = set()
    for rc in spec["retired_caves"]:
        old = retired_cells(rc, g)
        entry, _act, holder = restore_parts(rc)
        bounds = [old["bounds"]]
        succ = rc.get("successor")
        if succ:
            san = sans[succ]
            if not san.get("site"):
                raise SystemExit("%s has no site: python tools/sanctuaries.py author" % succ)
            bounds.append(geometry(spec, san, g)["bounds"])
        hold = "%d %d %d %d" % _union_box(*bounds)
        out += [("cmd", "forceload add " + hold), ("wait", 4), ("fn", entry),
                ("check", ("chunk_look", holder, 0, "players standing in the retired cave %s (its restore refused)" % rc["id"]))]
        if succ:
            out.append(("fn", "%s/%s" % (F, build_name(sans[succ]))))
            done.add(succ)
        out.append(("cmd", "forceload remove " + hold))
    for s in spec["sanctuaries"]:
        if s["id"] in done:
            continue
        hold = "%d %d %d %d" % _union_box(geometry(spec, s, g)["bounds"])
        out += [("cmd", "forceload add " + hold), ("wait", 4), ("fn", "%s/%s" % (F, build_name(s))), ("cmd", "forceload remove " + hold)]
    return out


def step_functions(spec=None):
    """Every function the step runs, from the committed data (the restores and the builds)."""
    spec = spec or load()
    out = [restore_parts(rc)[0] for rc in spec["retired_caves"]]
    out += ["%s/%s" % (F, build_name(s)) for s in spec["sanctuaries"]]
    return out


# ------------------------------------------------------------------ the records in other files

def habitat_records(spec, plan):
    d = spec["habitat_defaults"]
    out = []
    for e in plan:
        san, gm = e["san"], e["geometry"]
        x, y, z = gm["centre"]
        mimic = base(gm["cells"][(x, y, z)])
        for h in san.get("habitat") or []:
            rng = san["court"]["reach"]
            out.append({
                "id": h["id"], "place": "%s (%s, %s) in data/sanctuaries.json: the court's centre floor cell" % (san["name"], san["id"], san["kind"]),
                "pool": "cobblers:%s" % pool_of(h), "style": "activated", "replace_spawns": False,
                "position": {"x": x, "y": y, "z": z}, "mimic": mimic,
                "activated": {"spawn_range": rng, "chance": d["chance"], "trigger": d["trigger"], "cancel_range": d["cancel_range"],
                              "max_spawns": d["max_spawns"], "max_spawns_per_activation": d["max_spawns_per_activation"]},
                "status": d["status"], "generated_by": GENERATED,
                "why": "The court's occupants (tools/sanctuaries.py, an open-air sanctuary replacing the cave kit's chamber): one activated "
                       "block in the court's centre floor cell, spawn_range %d (the court's reach), cancel_range -1 so nothing is cancelled, "
                       "up to %d alive and %d refilled at a time. It is written after the sanctuary's build (the sanctuary step before R9E). "
                       "Whether an activated block's spawns stay inside an open court's walls is unmeasured (HB-1)."
                       % (rng, d["max_spawns"], d["max_spawns_per_activation"])})
    return out


def pool_records(spec, plan):
    habs, ents = [], []
    for e in plan:
        san, gm = e["san"], e["geometry"]
        sub, bmin, bmax, tier = band_of(gm["centre"][0], gm["centre"][2])
        for h in san.get("habitat") or []:
            p = h["pool"]
            pid = p["id"]
            lv = [level_range(x) for x in p["entries"]]
            lo, hi = min(a for a, _b in lv), max(b for _a, b in lv)
            rec_entries, flat = [], []
            for x, (a, b) in zip(p["entries"], lv):
                lvl = "%d-%d" % (a, b) if a != b else "%d" % a
                sid = species_id(x["species"])
                rec_entries.append({"species": x["species"], "pokemon": sid, "family": sid, "family_priority": x["family_priority"],
                                    "ambient": True, "eligibility_reason": x["reason"], "level": lvl, "bucket": x["bucket"],
                                    "weight": x["weight"], "conditions": {}})
                flat.append({"id": "habitat.%s.%s" % (pid, sid), "species": sid, "bucket": x["bucket"], "level": lvl, "weight": x["weight"],
                             "ambient": True, "scope": pid, "mechanism": "habitat_block", "conditions": {},
                             "eligibility_reason": x["reason"], "spawnable_position": "grounded"})
            habs.append({
                "id": pid, "display_name": p["display_name"],
                "intended_location": "%s (data/sanctuaries.json %s, %s) at x%d z%d: one activated Habitat Block, %s in data/habitat_blocks.json, "
                                     "in the court's centre floor" % (san["name"], san["id"], san["kind"], gm["centre"][0], gm["centre"][2], h["id"]),
                "mechanism": "habitat_block", "replace_spawns": False, "level_band": {"minimum": lo, "maximum": hi},
                "level_band_why": "the court's levels are set by its gate (%s), not by the sub-region (%s, %s-%s, tier %s)"
                                  % (", ".join(san["gate"]["flags"]), sub, bmin, bmax, tier),
                "why": p["why"], "entries": rec_entries,
                "placement_status": "authored: data/habitat_blocks.json %s, status planned (tools/sanctuaries.py)" % h["id"]})
            ents += flat
    return habs, ents


def probe_records(spec, plan, retired):
    """{'sanctuaries': [probe]} in data/world_probes.json's shape (tools/presence_audit.py extra)."""
    rows = []

    def blk(what, c, state):
        rows.append({"what": what, "block": [c[0], c[1], c[2], state], "expect": True})
    built = {}
    for e in plan:
        built.update(e["geometry"]["cells"])
    for e in plan:
        san, gm = e["san"], e["geometry"]
        sid = san["id"]
        cx, yf, cz = gm["centre"]
        cells = gm["cells"]
        blk("%s: air over the court's centre" % sid, (cx, yf + 2, cz), AIR)
        nb = (cx + 1, yf, cz)
        blk("%s: the court's floor beside its centre" % sid, nb, base(cells[nb]))
        hi = max((c for c, b in cells.items() if b != AIR), key=lambda c: (c[1], c[0], c[2]))
        blk("%s: the set piece's highest block" % sid, hi, base(cells[hi]))
        d = gm["barrier_cells"][0]
        blk("%s: the door's barrier (closed)" % sid, d, BARRIER)
        for h in san.get("habitat") or []:
            blk("%s: the Habitat Block %s" % (sid, h["id"]), (cx, yf, cz), "cobblemon:habitat_block")
        if san["occupant"]["mode"] == "area_boss":
            o = san["occupant"]
            rows.append({"what": "%s: the boss (one tagged %s once a champion has come near; absent while the clock runs)" % (sid, o["tag"]),
                         "hold": [cx, yf + 1, cz], "entity": "@e[type=cobblemon:pokemon,tag=%s]" % o["tag"], "count_max": 1})
    for r in retired:
        rc, gm = r["rc"], r["geometry"]
        c = (gm["centre"][0], gm["yh"] + 2, gm["centre"][2])
        want = built.get(c) or (AIR if c[1] > gm["ground"](c[0], c[2]) else (rc["terrain"]["deep"] if c[1] <= gm["ground"](c[0], c[2]) - 3 else rc["terrain"]["under"]))
        blk("%s (retired %s): the old chamber's middle, restored" % (rc["id"], rc["retired"]), c, base(want))
        for (x, y, z, b) in restore_probes(rc, gm):
            g = gm["ground"](x, z)
            t = rc["terrain"]
            want = built.get((x, y, z)) or (AIR if y > g else t["surface"] if y == g else t["under"] if y >= g - 2 else t["deep"])
            blk("%s (retired %s): the old %s, gone" % (rc["id"], rc["retired"], "barrier" if b == BARRIER else "probe block " + b), (x, y, z), base(want))
    return {"sanctuaries": rows}


def record_problems(spec, plan, retired):
    out = []
    blocks = {b["id"]: b for b in jload(HABITATS)["blocks"]}
    for want in habitat_records(spec, plan):
        if blocks.get(want["id"]) != want:
            out.append("data/habitat_blocks.json %s is missing or differs (python tools/sanctuaries.py author --resync)" % want["id"])
    sp = jload(SPAWNS)
    habs = {h["id"]: h for h in sp["habitats"]}
    flat = {e["id"]: e for e in sp["entries"]}
    wh, we = pool_records(spec, plan)
    for h in wh:
        if habs.get(h["id"]) != h:
            out.append("data/spawns.json habitats %s is missing or differs (python tools/sanctuaries.py author --resync)" % h["id"])
    for e in we:
        if flat.get(e["id"]) != e:
            out.append("data/spawns.json entries %s is missing or differs" % e["id"])
    gen = {b["id"] for b in blocks.values() if b.get("generated_by") == GENERATED}
    if gen != {w["id"] for w in habitat_records(spec, plan)}:
        out.append("data/habitat_blocks.json carries generated blocks the sanctuaries no longer name: %s" % sorted(gen - {w["id"] for w in habitat_records(spec, plan)}))
    old = {rc["cave"]["id"] for rc in spec["retired_caves"]}
    left = [b["id"] for b in blocks.values() if any(b["id"].startswith(o + "_") for o in old)]
    if left:
        out.append("data/habitat_blocks.json still carries a retired cave's block: %s" % left[:4])
    left = [h["id"] for h in sp["habitats"] if any(h["id"].startswith(o + "_") for o in old)]
    if left:
        out.append("data/spawns.json still carries a retired cave's pool: %s" % left[:4])
    probes = jload(PROBES)["places"]
    if probes.get("sanctuaries") != probe_records(spec, plan, retired)["sanctuaries"]:
        out.append("data/world_probes.json places.sanctuaries is missing or differs (python tools/sanctuaries.py author --resync)")
    stale = [p["what"] for p in probes.get("caves") or [] if any(p["what"].startswith(o + ":") for o in old)]
    if stale:
        out.append("data/world_probes.json places.caves still probes a retired cave: %s" % stale[:3])
    return out


def light_problems(plan):
    """Lanterns only, each standing on a post or hung under a block: no light block, torch, campfire or glowing block placed."""
    LIGHT = ("glowstone", "sea_lantern", "shroomlight", "torch", "campfire", "jack_o_lantern", "lantern", "end_rod", "beacon",
             "froglight", "redstone_lamp", "copper_bulb", "amethyst_cluster", "amethyst_bud", "magma_block", "crying_obsidian_UNUSED")
    out = []
    for e in plan:
        cells = e["geometry"]["cells"]
        for (x, y, z), b in cells.items():
            bb = base(b)
            if not any(k in bb for k in LIGHT):
                continue
            if bb != "minecraft:lantern":
                out.append("%s: %s at (%d, %d, %d) gives light (lanterns on posts only)" % (e["san"]["id"], bb, x, y, z))
                continue
            if "hanging=true" in b:
                above = cells.get((x, y + 1, z), AIR)
                if base(above) == AIR:
                    out.append("%s: a hanging lantern at (%d, %d, %d) hangs from nothing" % (e["san"]["id"], x, y, z))
            else:
                below = base(cells.get((x, y - 1, z), AIR))
                if not (below.endswith("_fence") or below.endswith("_wall") or below == "minecraft:chain"):
                    out.append("%s: a lantern at (%d, %d, %d) stands on %s, not a post" % (e["san"]["id"], x, y, z, below))
    return out


def pack_problems(spec, plan):
    """Every placed block that is a spawn condition must be allowed by a policy entry scoped to the sanctuaries."""
    out = []
    spawn = set(jload(ROOT / "data" / "spawn_blocks.json")["blocks"])
    policy = jload(ROOT / "data" / "spawn_block_policy.json")
    allowed = {b for w in policy["whitelist"] if POLICY_SCOPE in (w.get("scope") or "") for b in w["blocks"]}
    placed = {base(b) for e in plan for b in e["geometry"]["cells"].values()}
    for rc in spec["retired_caves"]:
        placed |= {base(v) for v in rc["terrain"].values() if isinstance(v, str) and v.startswith("minecraft:")}
    for b in sorted((placed & spawn) - allowed):
        out.append("places %s, a spawn condition (data/spawn_blocks.json), and no data/spawn_block_policy.json entry scoped to %s allows it"
                   % (b, POLICY_SCOPE))
    return out


def plan_json(spec, plan, retired, counts):
    sans = {}
    for e in plan:
        gm, san = e["geometry"], e["san"]
        sans[san["id"]] = {"kind": san["kind"], "style": san["style"], "centre": gm["centre"], "front": gm["front"], "floor": gm["yf"],
                           "bounds": gm["bounds"], "height": gm["height"], "cells": len(gm["cells"]), "cut": gm["cut"], "fill": gm["fill"],
                           "ante_zone": gm["ante_zone"], "door_box": gm["door_box"], "inside_zone": gm["inside_zone"],
                           "chamber_zone": gm["chamber_zone"], "occupant": {"mode": san["occupant"]["mode"], "species": san["occupant"]["species"]}}
    ret = {r["rc"]["id"]: {"bounds": r["geometry"]["bounds"], "cells": len(r["geometry"]["cells"]), "successor": r["rc"].get("successor")}
           for r in retired}
    return {"schema": "cobblers.derived.sanctuaries/1", "step_functions": step_functions(spec), "commands": counts,
            "sanctuaries": sans, "retired_caves": ret}


# ------------------------------------------------------------------ authoring

def dump_json(path, doc):
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def sync_records(spec, plan, retired):
    """Write the derived records. Replaces ours (by id) and drops every retired cave's, keeps every other record."""
    old = {rc["cave"]["id"] for rc in spec["retired_caves"]}

    def retired_id(i):
        return any(i.startswith(o + "_") for o in old)
    hb = jload(HABITATS)
    ours = {h["id"] for s in spec["sanctuaries"] for h in s.get("habitat") or []}
    hb["blocks"] = [b for b in hb["blocks"] if b["id"] not in ours and not retired_id(b["id"])] + habitat_records(spec, plan)
    dump_json(HABITATS, hb)
    sp = jload(SPAWNS)
    habs, ents = pool_records(spec, plan)
    pids = {h["id"] for h in habs}
    sp["habitats"] = [h for h in sp["habitats"] if h["id"] not in pids and not retired_id(h["id"])] + habs
    sp["entries"] = [e for e in sp["entries"] if e.get("scope") not in pids and not retired_id(e.get("scope") or "")] + ents
    dump_json(SPAWNS, sp)
    pr = jload(PROBES)
    pr["places"]["sanctuaries"] = probe_records(spec, plan, retired)["sanctuaries"]
    if "caves" in pr["places"]:
        pr["places"]["caves"] = [p for p in pr["places"]["caves"] if not any(p["what"].startswith(o + ":") for o in old)]
    dump_json(PROBES, pr)


def author(spec, only=None, source_root=None, inputs_root=None, resite=False):
    g0 = G.Ground(source_root)
    for san in spec["sanctuaries"]:
        if only and san["id"] != only:
            continue
        if san.get("site") and not resite:
            continue
        clear = clearance(spec, san, g0, inputs_root, need_packs=True)
        best = search(spec, san, g0, clear, 1)
        if not best:
            raise SystemExit("%s: no site passes every rule; nothing written" % san["id"])
        s, centre, front, yf, cut, fill = best[0]
        san["site"] = {"centre": centre, "front": front,
                       "sited_by": "tools/sanctuaries.py author: the best of search() (earthwork per platform column + distance from host_anchor / 40 "
                                   "+ 4 when the door faces away from it) over the canonical heightmap and the keep_clear rules"}
        print("%s: centre %s front %s floor y%d (score %s, cut %d, fill %d)" % (san["id"], centre, front, yf, s, cut, fill))
    plan, retired, probs, _n = model(spec, source_root, inputs_root, need_packs=True)
    unsited = [p for p in probs if p.endswith("no site (python tools/sanctuaries.py author)")]
    probs = [p for p in probs if p not in unsited]
    if probs:
        for p in probs:
            print("PROBLEM:", p)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    for p in unsited:
        print("NOTE (not yet sited; its records wait):", p)
    for e in plan:
        gm = e["geometry"]
        sub, bmin, bmax, tier = band_of(gm["centre"][0], gm["centre"][2])
        e["san"]["site"].update({"floor": gm["yf"], "court_centre": gm["centre"], "subregion": sub, "subregion_band": [bmin, bmax],
                                 "tier": tier, "height": gm["height"], "bounds": gm["bounds"]})
    dump_json(SPEC, spec)
    sync_records(spec, plan, retired)
    print("wrote data/sanctuaries.json and the derived records for %d sanctuaries" % len(plan))
    return 0


# ------------------------------------------------------------------ a look at them (for the owner and for review)

COLOURS = {"tuff": (108, 109, 102), "calcite": (222, 222, 216), "copper": (80, 160, 130), "deepslate": (70, 70, 74), "prismarine": (90, 160, 150),
           "stone_brick": (122, 122, 122), "mossy": (98, 120, 80), "cracked": (110, 110, 110), "red_sandstone": (186, 99, 40),
           "terracotta": (160, 82, 50), "blackstone": (42, 36, 40), "basalt": (80, 80, 86), "gilded": (200, 160, 40), "grass": (95, 150, 60),
           "dirt": (130, 95, 65), "moss": (90, 120, 50), "lantern": (250, 200, 90), "iron": (180, 180, 180), "chain": (60, 60, 70),
           "spruce": (110, 80, 50), "water": (50, 90, 200), "quartz": (235, 230, 225), "barrier": (220, 40, 40), "crying": (60, 20, 90),
           "smooth_stone": (160, 160, 160), "andesite": (135, 135, 135), "cobble": (110, 110, 110), "polished": (130, 130, 128),
           "gravel": (130, 125, 120), "coarse": (120, 90, 60), "podzol": (100, 70, 40), "snow": (240, 240, 245)}


def colour(block):
    b = base(block)[len("minecraft:"):]
    for k in sorted(COLOURS, key=len, reverse=True):
        if k in b:
            return COLOURS[k]
    h = int(hashlib.md5(b.encode()).hexdigest()[:6], 16)
    return ((h >> 16) & 255, (h >> 8) & 255, h & 255)


def render(spec, plan, out_dir=None, scale=6):
    """Per sanctuary, a front elevation (looking in from the forecourt) and a plan from above, as PNGs."""
    from PIL import Image
    out_dir = Path(out_dir or RENDERS)
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for e in plan:
        san, gm = e["san"], e["geometry"]
        p = gm["piece"]
        cells = {k: v for k, v in p.blocks.items() if v != AIR}
        for (u, d), b in p.floor.items():
            cells.setdefault((u, d, 0), b)
        us = [k[0] for k in cells]
        ds = [k[1] for k in cells]
        hs = [k[2] for k in cells]
        u0, u1, d0, d1, h0, h1 = min(us), max(us), min(ds), max(ds), min(hs), max(hs)
        W, H = u1 - u0 + 1, h1 - h0 + 1
        img = Image.new("RGB", (W * scale, H * scale), (200, 225, 240))
        px = img.load()
        best = {}
        for (u, d, h), b in cells.items():
            k = (u, h)
            if k not in best or d < best[k][0]:
                best[k] = (d, b)
        for (u, h), (d, b) in best.items():
            c = colour(b)
            shade = max(0.55, 1.0 - 0.012 * (d - d0))
            c = tuple(int(v * shade) for v in c)
            for a in range(scale):
                for bb in range(scale):
                    px[(u - u0) * scale + a, (h1 - h) * scale + bb] = c
        f1 = out_dir / ("%s_front.png" % san["id"])
        img.save(f1)
        D = d1 - d0 + 1
        img = Image.new("RGB", (W * scale, D * scale), (120, 160, 90))
        px = img.load()
        top = {}
        for (u, d, h), b in cells.items():
            if (u, d) not in top or h > top[(u, d)][0]:
                top[(u, d)] = (h, b)
        for (u, d), (h, b) in top.items():
            c = colour(b)
            shade = min(1.25, 0.75 + 0.025 * h)
            c = tuple(min(255, int(v * shade)) for v in c)
            for a in range(scale):
                for bb in range(scale):
                    px[(u - u0) * scale + a, (d1 - d) * scale + bb] = c
        f2 = out_dir / ("%s_plan.png" % san["id"])
        img.save(f2)
        f3 = out_dir / ("%s_iso.png" % san["id"])
        iso(gm).save(f3)
        made += [f1, f2, f3]
    return made


def iso(gm, s=8, view=0):
    """An isometric picture of the built cells and the graded land round them, seen from the forecourt's left front corner."""
    from PIL import Image, ImageDraw
    p = gm["piece"]
    cells = {}
    for (u, d, h), b in p.blocks.items():
        if b != AIR:
            cells[(u, d, h)] = b
    for (u, d), b in p.floor.items():
        cells.setdefault((u, d, 0), b)
    for (u, d) in gm["platform"]:
        cells.setdefault((u, d, 0), p.mix("apron", u, d, 0))
    for (u, d), hgt in p.drift.items():
        for h in range(1, hgt + 1):
            cells.setdefault((u, d, h), p.mix("drift_top", u, d, h))
    yf = gm["yf"]
    for (u, d), t in gm["band_top"].items():
        cells.setdefault((u, d, t - yf), p.mix("grade_top", u, d, t))

    def proj(u, d, h):
        return ((u + d) * s, (u - d) * s // 2 - h * s)
    pts = [proj(u, d, h) for (u, d, h) in cells]
    x0 = min(q[0] for q in pts) - 2 * s
    y0 = min(q[1] for q in pts) - 2 * s
    x1 = max(q[0] for q in pts) + 2 * s
    y1 = max(q[1] for q in pts) + 2 * s
    img = Image.new("RGB", (x1 - x0, y1 - y0), (205, 225, 240))
    dr = ImageDraw.Draw(img)
    for (u, d, h) in sorted(cells, key=lambda c: (c[0] - c[1], c[2])):
        b = cells[(u, d, h)]
        c = colour(b)
        X, Y = proj(u, d, h)
        X -= x0
        Y -= y0
        top = [(X, Y), (X + s, Y - s // 2), (X + 2 * s, Y), (X + s, Y + s // 2)]
        left = [(X, Y), (X + s, Y + s // 2), (X + s, Y + s // 2 + s), (X, Y + s)]
        right = [(X + s, Y + s // 2), (X + 2 * s, Y), (X + 2 * s, Y + s), (X + s, Y + s // 2 + s)]
        dr.polygon(left, fill=tuple(int(v * 0.72) for v in c))
        dr.polygon(right, fill=tuple(int(v * 0.86) for v in c))
        dr.polygon(top, fill=c)
    return img


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("site", "author", "report", "build", "render"))
    p.add_argument("sanctuary", nargs="?")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--resite", action="store_true")
    p.add_argument("--resync", action="store_true", help="accepted: author always re-writes the derived records")
    p.add_argument("--source-root")
    p.add_argument("--inputs-root", help="a full checkout holding build/datapacks, build/paint, derived/routes and derived/water_shape")
    p.add_argument("--out")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "author":
        return author(spec, a.sanctuary, a.source_root, a.inputs_root, a.resite)
    if a.mode == "site":
        san = next((s for s in spec["sanctuaries"] if s["id"] == a.sanctuary), None)
        if san is None:
            raise SystemExit("no sanctuary %r" % a.sanctuary)
        g0 = G.Ground(a.source_root)
        clear = clearance(spec, san, g0, a.inputs_root, need_packs=True)
        for o in search(spec, san, g0, clear, a.top):
            print(json.dumps(o))
        return 0
    if a.mode == "render":
        plan, _r, probs, _n = model(spec, a.source_root, a.inputs_root, clear_check=False)
        for f in render(spec, plan, a.out):
            print("wrote", f)
        for pr in probs:
            print("PROBLEM:", pr)
        return 0
    try:
        plan, retired, probs, notes = model(spec, a.source_root, a.inputs_root)
        g0 = G.Ground(a.source_root)
        if plan:
            probs += pack_problems(spec, plan) + record_problems(spec, plan, retired) + light_problems(plan)
        files = pack_files(spec, plan, retired, g0) if not probs else None
    except SanctuaryError as exc:
        raise SystemExit("FAILED: %s; nothing written" % exc)
    for e in plan:
        gm = e["geometry"]
        print("  %-26s %s %-12s centre %s front %-5s floor y%d  height %d  %d cells, cut %d fill %d  %s" % (
            e["san"]["id"], e["san"]["kind"], e["san"]["style"], gm["centre"], gm["front"], gm["yf"], gm["height"], len(gm["cells"]),
            gm["cut"], gm["fill"], e["san"]["occupant"]["mode"]))
    for r in retired:
        print("  retired %-20s %s: %d cells, successor %s" % (r["rc"]["id"], r["rc"]["cave"]["kind"], len(r["geometry"]["cells"]), r["rc"].get("successor")))
    for n in notes:
        print("  NOTE:", n)
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        print("report: %d sanctuaries, %d retired caves, 0 problems" % (len(plan), len(retired)))
        return 0
    counts = write(files)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan_json(spec, plan, retired, counts), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("wrote %s: %d sanctuaries, %d restores; plan %s" % (OUT.relative_to(ROOT), len(plan), len(retired), PLAN.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
