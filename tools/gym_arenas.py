#!/usr/bin/env python
"""The gym arenas: a hall carved below each gym where its leader is fought, from data/gym_arenas/<gym>.json.

The owner, 2026-10-08: leaders fight in cramped rooms. It should feel like a stage or a throne -- a long approach,
the leader raised at the far end, the arena floor between -- and it matters mechanically, because battles happen
in the world and a large Pokemon in a cramped room is inside the walls. Fixed lots, so carve below: the building is
the entrance and the arena opens beneath it, our own authored space. Each reads as its leader's. Big enough for the
largest Pokemon on the leader's team, MEASURED (tools/pokemon_sizes.py -> data/gym_arena_sizes.json). The juniors
and the puzzle route still lead to it: the descent starts where the puzzle route ends today, inside the building.

  python tools/gym_arenas.py check  [--gym gym1]          # build the model and prove every rule; writes nothing
  python tools/gym_arenas.py build  [--out <pack dir>]    # write build/datapacks/cobblers_gym_arenas
  python tools/gym_arenas.py survey [--write]             # the eight sites, for the arena authors
  python tools/gym_arenas.py probes [--write]             # presence probes into data/world_probes.json

ONE FILE PER GYM in data/gym_arenas/, so the authors of the eight arenas never touch the same file; the record
format is data/gym_arenas/SCHEMA.md. A theme is pure data: nothing in this tool is per gym.

THE SEAT. A leader's seat is authored in exactly one place: data/gym_arenas/<gym>.json leader.seat, once an arena
exists for that gym; before that, the building's leader.spawner (data/gym_buildings) or Misty's template spawner
(data/gym_interiors.json expect_spawner_at). leader_seats() below is the one reader every consumer uses
(tools/challenge_mode.py normal_seat, tools/route_trainers.py leader_cycle_lines, tools/trainer_world_audit.py,
tools/nuzlocke_map.py). The building keeps placing its spawner in the hall (tools/gym_buildings.py and its
audits are unchanged); the arena step R16GA then MOVES it: the new spawner in the arena, the old cell back to its
floor, any leader standing in the building removed. R16G also runs each seat move straight after the buildings,
so `--only R16G` never leaves a leader two spawners; the move waits until its arena stands. A building spawner is
therefore only ever the arena's starting point.

WHAT THIS TOOL REFUSES TO WRITE, each derived in docs/world-building/GYM_ARENAS.md "Design rules":
  bounds        every write inside the record's bounds or a declared through_building box; the arena's x/z inside
                its spawn-free zone (data/spawn_suppression.json), which is snapped to the 8-block grid
  cover         every write outside the building has COVER natural blocks between it and the lowest thing written
                above it (the ground, the lot's pad, the building's lowest course)
  shell         no open cell of the arena touches unwritten ground: a natural cave can never open into it
  seat          one spawner at leader.seat, powered from below, flush in the dais, two air over it
  dais          the leader raised 2 to 5 over the floor; the leader's stand not reachable on foot
  markers       Cobblemon Battle Positions' four blocks, each where its search finds it from every cell a battle
                can start (horizontalSearchRadius / verticalSearchRange from the mod's config)
  clear disc    no solid within the leader's clear radius of either Pokemon marker, up to the clear height
  approach      the arena's first floor cell farther from the leader than rctmod's forceBattleMaxDistance + 1
  light         no cell a player stands on at block light 0
  commands      tools/function_limits.py: fills under 32,768 blocks, every write in a force-loaded chunk
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "gym_arenas"
SIZES = ROOT / "data" / "gym_arena_sizes.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_gym_arenas"
NS = "cobblers"
FOLDER = "gym_arenas"
SCHEMA = "gym_arena/1"
SPAWNER = "rctmod:trainer_spawner"
REDSTONE = "minecraft:redstone_block"
HEALER = "cobblemon:healing_machine"
MARKERS = {"trainer_pokemon": "cobblemonbattlepositions:trainer_pokemon_position",
           "player_pokemon": "cobblemonbattlepositions:player_pokemon_position",
           "trainer_stand": "cobblemonbattlepositions:trainer_stand_position",
           "player_stand": "cobblemonbattlepositions:player_stand_position"}
# Natural blocks between the arena's outermost write and whatever is written above it. Two: one is the cover itself,
# and one more because round(heightmap) matches an export at 99.85% of columns and the rest are one block LOW
# (tools/ground.py, measured 2026-09-20): with one block of cover the shell would be bare sky at those columns.
COVER = 2
# vanilla monsters spawn only at block light 0 (1.18+); MobsBeGone removes them in this pack, so this is the floor
# the arena keeps anyway, not a look. How light a hall LOOKS is reported, not gated.
MIN_LIGHT = 1
# a sprinting player covers 5.612 blocks a second; rctmod starts a battle on sight after forceBattleLookTicks
SPRINT_PER_TICK = 5.612 / 20.0
OPS = ("comment", "fill", "carve", "shell", "setblock", "scatter", "repeat", "newel_stair", "straight_stair")
LIGHT = {"minecraft:lantern": 15, "minecraft:soul_lantern": 10, "minecraft:torch": 14, "minecraft:wall_torch": 14,
         "minecraft:soul_torch": 10, "minecraft:soul_wall_torch": 10, "minecraft:glowstone": 15,
         "minecraft:sea_lantern": 15, "minecraft:shroomlight": 15, "minecraft:ochre_froglight": 15,
         "minecraft:verdant_froglight": 15, "minecraft:pearlescent_froglight": 15, "minecraft:end_rod": 14,
         "minecraft:jack_o_lantern": 15, "minecraft:campfire": 15, "minecraft:soul_campfire": 10,
         "minecraft:magma_block": 3}
OPEN_EXACT = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:water", "minecraft:lava",
              "minecraft:ladder", "minecraft:chain", "minecraft:lantern", "minecraft:soul_lantern", "minecraft:torch",
              "minecraft:wall_torch", "minecraft:soul_torch", "minecraft:soul_wall_torch", "minecraft:light",
              "minecraft:redstone_wire", "minecraft:rail", "minecraft:end_rod", "minecraft:scaffolding"}
OPEN_PARTS = ("_carpet", "_pressure_plate", "_button", "_sign", "_banner", "_candle", "_sapling", "flower_pot")
# partial blocks: not a cube (a wall's face is not flush), but a player stands on them and they stop a Pokemon
PARTIAL_PARTS = ("_stairs", "_slab", "_wall", "_fence", "_fence_gate", "_trapdoor", "iron_bars", "_pane")

# The ground rule (tools/ground_rule.py): ground comes from tools/ground.py; only verify() reads a world, to CHECK
WORLD_READS = set()


class ArenaError(SystemExit):
    pass


# ----------------------------------------------------------------------------------------------------- loading
def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def records(only=None):
    out = []
    for p in sorted(DATA.glob("gym*.json")):
        doc = load(p)
        if doc.get("schema") != SCHEMA:
            raise ArenaError("%s: schema is %r, expected %r" % (p.name, doc.get("schema"), SCHEMA))
        if doc["id"] != p.stem:
            raise ArenaError("%s: record id %r does not match its file name" % (p.name, doc["id"]))
        if only and doc["id"] != only:
            continue
        out.append((p, doc))
    if only and not out:
        raise ArenaError("no data/gym_arenas/%s.json" % only)
    return out


_SEATS = {}


def leader_seats():
    """{leader id: {"gym", "seat", "old_seat", "source"}} for every gym, the one reader of a leader's seat.

    An arena record's leader.seat wins; else the building's leader.spawner (data/gym_buildings); else the template
    spawner data/gym_interiors.json measured (Misty's). Reads JSON only, never a world, never a heavy import;
    remembered until one of the files it read changes."""
    files = sorted((ROOT / "data" / "gym_buildings").glob("gym*.json")) + sorted(DATA.glob("gym*.json")) + \
        [ROOT / "data" / "gym_interiors.json"]
    key = tuple((str(p), p.stat().st_mtime_ns) for p in files)
    if key not in _SEATS:
        _SEATS.clear()
        _SEATS[key] = _leader_seats()
    return {k: dict(v) for k, v in _SEATS[key].items()}


def _leader_seats():
    out = {}
    for p in sorted((ROOT / "data" / "gym_buildings").glob("gym*.json")):
        g = load(p)
        lead = g.get("leader") or {}
        if lead.get("id") and lead.get("spawner"):
            out[lead["id"]] = {"gym": g["id"], "seat": tuple(lead["spawner"]), "old_seat": None,
                               "source": "data/gym_buildings/%s leader.spawner" % p.name}
    for g in load(ROOT / "data" / "gym_interiors.json")["gyms"]:
        lead = g.get("leader") or {}
        if g.get("built") and lead.get("id") and lead.get("expect_spawner_at") and lead["id"] not in out:
            out[lead["id"]] = {"gym": g["id"], "seat": tuple(lead["expect_spawner_at"]), "old_seat": None,
                               "source": "data/gym_interiors.json %s leader.expect_spawner_at" % g["id"]}
    for p in sorted(DATA.glob("gym*.json")):
        a = load(p)
        lead = a.get("leader") or {}
        if not (lead.get("id") and lead.get("seat")):
            continue
        before = out.get(lead["id"])
        out[lead["id"]] = {"gym": a["id"], "seat": tuple(lead["seat"]),
                           "old_seat": before["seat"] if before else None,
                           "source": "data/gym_arenas/%s leader.seat" % p.name}
    return out


def seat_of(leader_id):
    s = leader_seats().get(leader_id)
    return s["seat"] if s else None


def building_doc(gym):
    p = ROOT / "data" / "gym_buildings" / ("%s.json" % gym)
    return load(p) if p.exists() else None


def interior_doc(gym):
    for g in load(ROOT / "data" / "gym_interiors.json")["gyms"]:
        if g["id"] == gym:
            return g
    return None


def zone_box(zone_id):
    for z in load(ROOT / "data" / "spawn_suppression.json")["spawn_free_zones"]:
        if z["id"] == zone_id:
            return tuple(z["box"])
    raise ArenaError("data/spawn_suppression.json has no spawn-free zone %r" % zone_id)


def battle_positions_config():
    """Cobblemon Battle Positions' server config: the overlay's copy if we ship one, else the base pack's."""
    for p in (ROOT / "modpack" / "config" / "cobblemonbattlepositions.json",
              ROOT / "base-pack" / "cobbleverse" / "config" / "cobblemonbattlepositions.json"):
        if p.exists():
            d = load(p)
            return {"h": int(d["horizontalSearchRadius"]), "v": int(d["verticalSearchRange"]),
                    "offset": float(d["spawnHeightOffset"]), "from": str(p.relative_to(ROOT))}
    raise ArenaError("no cobblemonbattlepositions.json in modpack/config or base-pack/cobbleverse/config")


def rct_config():
    """rctmod's forceBattleMaxDistance and forceBattleLookTicks (modpack/config/rctmod-server.toml)."""
    out = {}
    for line in (ROOT / "modpack" / "config" / "rctmod-server.toml").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        for k in ("forceBattleMaxDistance", "forceBattleLookTicks"):
            if s.startswith(k) and "=" in s:
                out[k] = float(s.split("=", 1)[1].strip())
    if len(out) != 2:
        raise ArenaError("modpack/config/rctmod-server.toml lacks forceBattleMaxDistance or forceBattleLookTicks")
    return out


def leader_size(leader_id):
    """The leader's design figures from data/gym_arena_sizes.json, keyed by upstream trainer id."""
    d = load(SIZES)
    for rec_id, L in d["leaders"].items():
        if L["upstream"] == leader_id:
            return dict(L["design"], width=L["largest_by_width"]["width"], record=rec_id)
    raise ArenaError("data/gym_arena_sizes.json has no leader %s: run tools/pokemon_sizes.py --write" % leader_id)


# ---------------------------------------------------------------------------------------------- block helpers
def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def is_open(state):
    """A cell a player's body and a Pokemon pass through."""
    n = block_name(state)
    return n in OPEN_EXACT or any(n.endswith(p) or p in n for p in OPEN_PARTS)


def is_partial(state):
    n = block_name(state)
    return any(p in n for p in PARTIAL_PARTS)


def norm(box):
    x0, y0, z0, x1, y1, z1 = box
    return (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1))


def inside(c, box):
    x0, y0, z0, x1, y1, z1 = norm(box)
    return x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and z0 <= c[2] <= z1


DIRS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def dir_of(dx, dz):
    for k, v in DIRS.items():
        if v == (dx, dz):
            return k
    raise ArenaError("not a cardinal step: %s" % ((dx, dz),))


# ------------------------------------------------------------------------------------------------- the model
class Arena:
    """The arena's commands and the voxel model of what they leave, built together, over the gym building's own
    model (tools/gym_buildings.py build_one) where the two meet, over the canonical heightmap elsewhere."""

    def __init__(self, doc, ground, building_at=None, building_bounds=None):
        self.doc = doc
        self.ground = ground
        self.building_at = building_at
        self.building_bounds = norm(building_bounds) if building_bounds else None
        self.palette = doc.get("palette") or {}
        self.allowed = set(doc.get("blocks") or [])
        self.ops = []
        self.cells = {}
        self.written = 0
        # the seat and its redstone: the build never writes them, so a re-run never takes the spawner away (the seat
        # function sets them, once, and the move is the only thing that ever does)
        sx, sy, sz = doc["leader"]["seat"]
        self.protect = {(sx, sy, sz), (sx, sy - 1, sz)}

    # ---- states
    def state(self, s):
        if s.startswith("$"):
            k = s[1:]
            if k not in self.palette:
                raise ArenaError("%s: palette has no %r" % (self.doc["id"], k))
            s = self.palette[k]
        n = block_name(s)
        if n == HEALER:
            raise ArenaError("%s: no gym may hold a healing machine" % self.doc["id"])
        if n not in self.allowed:
            raise ArenaError("%s: %s is not in the record's `blocks` list" % (self.doc["id"], n))
        return s

    # ---- writers
    def comment(self, text):
        self.ops.append("# %s" % text)

    def fill(self, box, state, mode=None):
        x0, y0, z0, x1, y1, z1 = norm(box)
        st = self.state(state)
        hit = [c for c in self.protect if inside(c, (x0, y0, z0, x1, y1, z1))]
        if hit and mode:
            raise ArenaError("%s: a %s fill over the seat %s: use plain fills there" % (self.doc["id"], mode, hit))
        boxes = [(x0, y0, z0, x1, y1, z1)]
        for c in hit:
            boxes = [p for b in boxes for p in subtract(b, c)]
        for b in boxes:
            self.ops.append("fill %d %d %d %d %d %d %s%s" % (b + (st, (" " + mode) if mode else "")))
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    if (x, y, z) in self.protect:
                        continue
                    edge = x in (x0, x1) or y in (y0, y1) or z in (z0, z1)
                    if mode in ("hollow", "outline") and not edge:
                        if mode == "hollow":
                            self.cells[(x, y, z)] = "minecraft:air"
                        continue
                    if mode == "keep" and not is_open(self.at(x, y, z)):
                        continue
                    self.cells[(x, y, z)] = st
                    self.written += 1

    def set(self, pos, state, seat=False):
        st = self.state(state)
        x, y, z = pos
        if (x, y, z) in self.protect and not seat:
            raise ArenaError("%s: a setblock on the seat %s: only the seat function writes there"
                             % (self.doc["id"], list(pos)))
        self.ops.append("setblock %d %d %d %s" % (x, y, z, st))
        self.cells[(x, y, z)] = st
        self.written += 1

    # ---- reading the model
    def natural(self, x, y, z):
        if self.building_at and self.building_bounds and inside((x, y, z), self.building_bounds):
            return self.building_at(x, y, z)
        return "minecraft:stone" if y <= self.ground(x, z) else "minecraft:air"

    def at(self, x, y, z):
        c = self.cells.get((x, y, z))
        return c if c is not None else self.natural(x, y, z)


# ------------------------------------------------------------------------------------------------------ the ops
def subtract(box, c):
    """The box without the one cell c, as up to six boxes."""
    x0, y0, z0, x1, y1, z1 = box
    x, y, z = c
    if not (x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1):
        return [box]
    out = []
    if y0 <= y - 1:
        out.append((x0, y0, z0, x1, y - 1, z1))
    if y + 1 <= y1:
        out.append((x0, y + 1, z0, x1, y1, z1))
    if x0 <= x - 1:
        out.append((x0, y, z0, x - 1, y, z1))
    if x + 1 <= x1:
        out.append((x + 1, y, z0, x1, y, z1))
    if z0 <= z - 1:
        out.append((x, y, z0, x, y, z - 1))
    if z + 1 <= z1:
        out.append((x, y, z + 1, x, y, z1))
    return out


def shift(part, d):
    """A copy of a part with every coordinate moved by d = (dx, dy, dz)."""
    dx, dy, dz = d
    p = dict(part)
    if "box" in p and len(p["box"]) == 6:
        b = p["box"]
        p["box"] = [b[0] + dx, b[1] + dy, b[2] + dz, b[3] + dx, b[4] + dy, b[5] + dz]
    if "pos" in p:
        p["pos"] = [p["pos"][0] + dx, p["pos"][1] + dy, p["pos"][2] + dz]
    if "positions" in p:
        p["positions"] = [[q[0] + dx, q[1] + dy, q[2] + dz] for q in p["positions"]]
    if "from" in p:
        p["from"] = [p["from"][0] + dx, p["from"][1] + dy, p["from"][2] + dz]
    if "parts" in p:
        p["parts"] = [shift(q, d) for q in p["parts"]]
    for k in ("top_y", "bottom_y"):
        if k in p:
            p[k] = p[k] + dy
    if "ring" in p:
        r = p["ring"]
        p["ring"] = [r[0] + dx, r[1] + dz, r[2] + dx, r[3] + dz]
    return p


def ring_path(x0, z0, x1, z1, start, turn):
    """The outer ring of the rectangle, as cells in walking order from `start`, clockwise ('cw', seen from above:
    east along the north side) or counter-clockwise."""
    cells = [(x, z0) for x in range(x0, x1 + 1)] + [(x1, z) for z in range(z0 + 1, z1 + 1)] + \
            [(x, z1) for x in range(x1 - 1, x0 - 1, -1)] + [(x0, z) for z in range(z1 - 1, z0, -1)]
    if turn == "ccw":
        cells = [cells[0]] + cells[:0:-1]
    s = tuple(start)
    if s not in cells:
        raise ArenaError("newel_stair start %s is not on the ring of %s" % (list(s), [x0, z0, x1, z1]))
    i = cells.index(s)
    return cells[i:] + cells[:i]


def newel_stair(a, part):
    """A winding stair round a solid newel, inside the rectangle `ring` [x0, z0, x1, z1] (its outer cells are the
    walk, everything inside them the newel). Down from top_y to bottom_y (the treads' block y), turning `turn`; a
    corner is a full-block landing, so a player walks it both ways. top_y is level with the floor the stair leaves
    (its back is flush with it). Headroom `headroom` cells is carved over every tread first. `wall` encloses the
    ring from bottom_y - 1 to wall_to_y."""
    x0, z0, x1, z1 = part["ring"]
    if x1 - x0 < 2 or z1 - z0 < 2:
        raise ArenaError("newel_stair ring %s: at least 3 by 3" % part["ring"])
    top, bottom = int(part["top_y"]), int(part["bottom_y"])
    head = int(part.get("headroom", 3))
    path = ring_path(x0, z0, x1, z1, part["start"], part.get("turn", "cw"))
    corners = {(x0, z0), (x1, z0), (x0, z1), (x1, z1)}
    steps, y, i = [], top, 0
    while True:
        c = path[i % len(path)]
        nxt = path[(i + 1) % len(path)]
        steps.append((c, y, nxt))
        if y == bottom:
            break
        # into a corner, down one (the landing is a full block level with the next stair's back); out of a corner,
        # level (that stair's back meets the landing); anywhere else down one. Walking UP, every step is then a
        # stair's half-block front or level, never a full block's +1: the stair is walked both ways without a jump
        if nxt in corners or c not in corners:
            y -= 1
        i += 1
        if i > 4 * len(path) * (top - bottom + 2):
            raise ArenaError("newel_stair never reaches bottom_y")
    a.comment("newel stair: %d treads from y%d to y%d round a newel in %s" % (len(steps), top, bottom, part["ring"]))
    under = part.get("under") or part["newel"]
    if part.get("wall"):
        wt = int(part.get("wall_to_y", top))
        for (wx0, wz0, wx1, wz1) in ((x0 - 1, z0 - 1, x1 + 1, z0 - 1), (x0 - 1, z1 + 1, x1 + 1, z1 + 1),
                                     (x0 - 1, z0, x0 - 1, z1), (x1 + 1, z0, x1 + 1, z1)):
            a.fill((wx0, bottom - 1, wz0, wx1, wt, wz1), part["wall"])
    a.fill((x0 + 1, bottom - 1, z0 + 1, x1 - 1, top, z1 - 1), part["newel"])
    # the ring solid first, so nothing between two treads is left as the rock it was cut from
    for (rx0, rz0, rx1, rz1) in ((x0, z0, x1, z0), (x0, z1, x1, z1), (x0, z0 + 1, x0, z1 - 1), (x1, z0 + 1, x1, z1 - 1)):
        a.fill((rx0, bottom - 1, rz0, rx1, top - 1, rz1), under)
    for (cx, cz), ty, _n in steps:
        a.fill((cx, ty + 1, cz, cx, ty + head, cz), "minecraft:air")
    for (cx, cz), ty, (nx, nz) in steps:
        if (cx, cz) in corners or ty == bottom:
            a.set((cx, ty, cz), part["landing"])
        else:
            down = dir_of(nx - cx, nz - cz)
            a.set((cx, ty, cz), "%s[facing=%s,half=bottom,shape=straight]" % (a.state(part["tread"]),
                                                                                 OPPOSITE[down]))
    return [(c, y) for c, y, _n in steps]


def straight_stair(a, part):
    """A straight stair `steps` treads down from `from` in `dir`, `width` wide to the right of the walk (facing the
    way down), with `headroom` carved over every tread and the cell under each set to `under`."""
    x, y, z = part["from"]
    dx, dz = DIRS[part["dir"]]
    rx, rz = -dz, dx
    w = int(part.get("width", 1))
    head = int(part.get("headroom", 3))
    for i in range(int(part["steps"])):
        for j in range(w):
            cx, cz, ty = x + dx * i + rx * j, z + dz * i + rz * j, y - i
            a.fill((cx, ty + 1, cz, cx, ty + head, cz), "minecraft:air")
            a.set((cx, ty - 1, cz), part["under"])
            a.set((cx, ty, cz), "%s[facing=%s,half=bottom,shape=straight]" % (a.state(part["tread"]),
                                                                               OPPOSITE[part["dir"]]))


def run_parts(a, parts, where="parts"):
    for i, part in enumerate(parts):
        op = part.get("op")
        if op not in OPS:
            raise ArenaError("%s %s[%d]: op %r is not one of %s" % (a.doc["id"], where, i, op, ", ".join(OPS)))
        if part.get("why"):
            a.comment(part["why"])
        if op == "comment":
            continue
        if op == "fill":
            a.fill(part["box"], part["block"], part.get("mode"))
        elif op == "carve":
            a.fill(part["box"], "minecraft:air")
        elif op == "shell":
            # the six faces, `thickness` deep, then the inside carved: never a solid fill of the whole box, which
            # would bury a leader standing in it for the length of the function
            t = int(part.get("thickness", 2))
            x0, y0, z0, x1, y1, z1 = norm(part["box"])
            for f in ((x0, y0, z0, x1, y0 + t - 1, z1), (x0, y1 - t + 1, z0, x1, y1, z1),
                      (x0, y0 + t, z0, x0 + t - 1, y1 - t, z1), (x1 - t + 1, y0 + t, z0, x1, y1 - t, z1),
                      (x0 + t, y0 + t, z0, x1 - t, y1 - t, z0 + t - 1), (x0 + t, y0 + t, z1 - t + 1, x1 - t, y1 - t, z1)):
                a.fill(f, part["block"])
            a.fill((x0 + t, y0 + t, z0 + t, x1 - t, y1 - t, z1 - t), "minecraft:air")
        elif op == "setblock":
            a.set(part["pos"], part["block"])
        elif op == "scatter":
            for p in part["positions"]:
                a.set(p, part["block"])
        elif op == "repeat":
            dx, dy, dz = part["step"]
            for k in range(int(part["count"])):
                run_parts(a, [shift(q, (dx * k, dy * k, dz * k)) for q in part["parts"]],
                          "%s[%d].parts" % (where, i))
        elif op == "newel_stair":
            newel_stair(a, part)
        elif op == "straight_stair":
            straight_stair(a, part)


def place_markers(a, doc):
    b = doc["battle"]
    a.comment("Cobblemon Battle Positions: the four blocks its search finds from the challenger's feet")
    for k, block in MARKERS.items():
        a.allowed.add(block)
        a.set(b[k], block)


def place_seat(a, doc):
    """The seat as the move leaves it: the spawner flush in the dais, its redstone under it."""
    x, y, z = doc["leader"]["seat"]
    a.allowed |= {SPAWNER, REDSTONE}
    a.set((x, y - 1, z), REDSTONE, seat=True)
    a.set((x, y, z), '%s{TrainerIds:["%s"]}' % (SPAWNER, doc["leader"]["id"]), seat=True)


# --------------------------------------------------------------------------------------------- the site's ground
def lot_of(doc):
    """(lot rect, lot level) of the gym, from the town plan in data/placements.json."""
    import gym_buildings as GB
    b = building_doc(doc["gym"])
    if b:
        return GB.gym_lot(b["settlement"])
    i = interior_doc(doc["gym"])
    plan = load(ROOT / "data" / "placements.json")["settlements"][i["settlement"]]["plan"]
    for an in plan.get("anchors") or []:
        if "gym" in (an.get("role") or ""):
            return list(an["rect"]), an.get("level")
    raise ArenaError("%s: no gym anchor in data/placements.json" % doc["gym"])


def building_model(gym):
    """(at, bounds, min write y, doc) of the gym's own building as R16G leaves it, or Nones (gym 2)."""
    import gym_buildings as GB
    b = building_doc(gym)
    if not b:
        return None, None, None, None
    e, _rect, _lvl = GB.build_one(b)
    ys = [c[1] for c in e.cells]
    return e.at, tuple(b["bounds"]), min(ys), b


def natural_top(x, z, G, lot, lot_level, bbounds, bmin):
    """The highest NATURAL block of a column: under the building, below its lowest course; on the lot, below the
    prep's pad; elsewhere the ground itself."""
    top = G(x, z)
    x0, z0, x1, z1 = lot
    if x0 <= x <= x1 and z0 <= z <= z1 and lot_level is not None:
        top = min(top, int(lot_level) - 1)
    if bbounds is not None:
        bx0, _by0, bz0, bx1, _by1, bz1 = norm(bbounds)
        if bx0 <= x <= bx1 and bz0 <= z <= bz1:
            top = min(top, bmin - 1)
    return top


# ---------------------------------------------------------------------------------------------- building it
def build(doc, G=None):
    """(Arena, problems, facts) for one record."""
    import ground as ground_mod
    G = G or ground_mod.load()
    at_b, bbounds, bmin, bdoc = building_model(doc["gym"])
    a = Arena(doc, G, at_b, bbounds)
    a.comment("%s: %s (data/gym_arenas/%s.json, tools/gym_arenas.py). After R16G: the building stands first."
              % (doc["id"], doc.get("name", ""), doc["id"]))
    run_parts(a, doc["parts"])
    place_markers(a, doc)
    build_ops = list(a.ops)
    place_seat(a, doc)
    problems, facts = check(doc, a, G, bdoc, bbounds, bmin)
    return a, build_ops, problems, facts


# ------------------------------------------------------------------------------------------------ the checks
def check(doc, a, G, bdoc, bbounds, bmin):
    bad, facts = [], {}
    gid = doc["id"]
    lead = doc["leader"]
    lot, lot_level = lot_of(doc)
    bounds = norm(doc["bounds"])
    through = [norm(t["box"]) for t in doc.get("through_building") or []]
    zone = zone_box(doc["spawn_free_zone"])
    bp, rct = battle_positions_config(), rct_config()
    size = leader_size(lead["id"])
    reach = rct["forceBattleMaxDistance"] + 1
    facts.update({"cells_written": a.written, "bounds": list(bounds), "zone": list(zone),
                  "battle_positions": bp, "rct": rct, "size": size})

    # bounds, zone, through_building
    zx0, zz0, zx1, zz1 = zone
    if not (zx0 <= bounds[0] and bounds[3] <= zx1 and zz0 <= bounds[2] and bounds[5] <= zz1):
        bad.append("bounds %s leave the spawn-free zone %s %s: extend the zone (8-block grid) or shrink the arena"
                   % (list(bounds), doc["spawn_free_zone"], list(zone)))
    for (x, z) in ((zx0, zz0), (zx1 + 1, zz1 + 1)):
        if x % 8 or z % 8:
            bad.append("spawn-free zone %s is not on the 8-block grid the suppression is written on" % list(zone))
    stray, in_bld, uncovered = [], [], []
    for c in a.cells:
        in_t = any(inside(c, t) for t in through)
        if not inside(c, bounds) and not in_t:
            stray.append(c)
        if bbounds and inside(c, bbounds) and not in_t:
            in_bld.append(c)
    if stray:
        bad.append("%d write(s) outside bounds and every through_building box, first %s" % (len(stray), list(stray[0])))
    if in_bld:
        bad.append("%d write(s) inside the building's bounds but in no through_building box, first %s"
                   % (len(in_bld), list(in_bld[0])))

    # cover: the highest arena write per column, against the natural top
    tops = {}
    for (x, y, z) in a.cells:
        if any(inside((x, y, z), t) for t in through):
            continue
        tops[(x, z)] = max(tops.get((x, z), -999), y)
    worst = None
    for (x, z), y in tops.items():
        nt = natural_top(x, z, G, lot, lot_level, bbounds, bmin)
        slack = nt - COVER - y
        if worst is None or slack < worst[0]:
            worst = (slack, (x, y, z), nt)
        if slack < 0:
            uncovered.append((x, y, z, nt))
    if uncovered:
        u = uncovered[0]
        bad.append("%d column(s) with fewer than %d natural blocks over the arena, first (%d, %d, %d) under a "
                   "natural top at y%d" % (len(uncovered), COVER, u[0], u[1], u[2], u[3]))
    facts["cover_slack_min"] = worst[0] if worst else None

    # the route the building already has must not be cut
    if bdoc:
        cut = []
        for st in bdoc.get("route") or []:
            for k in ("from", "to"):
                if st.get(k):
                    x, y, z = st[k]
                    for c in ((x, y - 1, z), (x, y, z), (x, y + 1, z)):
                        if c in a.cells and c != tuple(doc["entry"]["route_end"]):
                            cut.append((st.get("id"), k, c))
        if cut:
            bad.append("the arena writes on the building's own route: %s" % cut[:3])

    # shell: no open arena cell touches unwritten natural ground
    leak = []
    for c, s in a.cells.items():
        if not is_open(s):
            continue
        x, y, z = c
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + d[0], y + d[1], z + d[2])
            if n in a.cells:
                continue
            if bbounds and inside(n, bbounds):
                continue
            leak.append((c, n))
    if leak:
        bad.append("%d open cell(s) of the arena touch unwritten ground (the shell must be built, never the rock), "
                   "first %s beside %s" % (len(leak), list(leak[0][0]), list(leak[0][1])))

    # the seat
    import npc_spot_sweep as sweep
    sx, sy, sz = lead["seat"]
    if not inside((sx, sy, sz), bounds):
        bad.append("leader.seat %s is outside the arena's bounds" % list(lead["seat"]))
    why = sweep.spawner_problem(a.at, (sx, sy, sz))
    if why:
        bad.append(why)
    for dy in (1, 2):
        if not is_open(a.at(sx, sy + dy, sz)):
            bad.append("the seat needs two open cells over it; %s is %s" % ([sx, sy + dy, sz], a.at(sx, sy + dy, sz)))
    spawners = [c for c, s in a.cells.items() if block_name(s) == SPAWNER]
    if spawners != [(sx, sy, sz)]:
        bad.append("the arena writes spawners at %s; exactly one, at leader.seat" % spawners)
    fy = int(doc["floor_y"])
    h = sy - fy
    facts["dais_height"] = h
    if not (2 <= h <= bp["v"] + 2):
        bad.append("the dais is %d over the floor: at least 2 so a player cannot step or jump onto it, at most "
                   "verticalSearchRange + 2 = %d so the trainer stand is found from the floor" % (h, bp["v"] + 2))

    # markers
    b = doc["battle"]
    for k in ("trainer_pokemon", "player_pokemon", "player_stand"):
        mx, my, mz = b[k]
        if my != fy - 1:
            bad.append("battle.%s at y%d: put it one under the floor's top course (y%d), so spawnHeightOffset %.1f "
                       "lands its occupant on the floor" % (k, my, fy - 1, bp["offset"]))
        if is_open(a.at(mx, fy, mz)) or is_partial(a.at(mx, fy, mz)):
            bad.append("battle.%s: the floor over it at %s is %s, not a full block" % (k, [mx, fy, mz],
                                                                                     a.at(mx, fy, mz)))
    tx, ty, tz = b["trainer_stand"]
    if ty != sy - 1:
        bad.append("battle.trainer_stand at y%d: one under the dais top (y%d)" % (ty, sy - 1))
    if is_open(a.at(tx, ty + 1, tz)) or not is_open(a.at(tx, ty + 2, tz)) or not is_open(a.at(tx, ty + 3, tz)):
        bad.append("battle.trainer_stand %s: the dais top over it must be a block with two open cells above"
                   % list(b["trainer_stand"]))

    # clear discs round the two Pokemon markers
    R, H, W = float(size["clear_radius"]), float(size["clear_height"]), float(size["width"])
    top = fy + int(math.ceil(H)) + 1
    for k in ("trainer_pokemon", "player_pokemon"):
        mx, _my, mz = b[k]
        cx, cz = mx + 0.5, mz + 0.5
        hits = []
        for x in range(int(cx - R) - 2, int(cx + R) + 3):
            for z in range(int(cz - R) - 2, int(cz + R) + 3):
                ddx = max(x - cx, 0.0, cx - (x + 1))
                ddz = max(z - cz, 0.0, cz - (z + 1))
                if math.hypot(ddx, ddz) >= R:
                    continue
                for y in range(fy + 1, top + 1):
                    if not is_open(a.at(x, y, z)):
                        hits.append((x, y, z))
                        break
        if hits:
            bad.append("battle.%s: %d column(s) with a block within the clear radius %.2f (%s) up to y%d, first %s"
                       % (k, len(hits), R, size["clear_radius_species"], top, list(hits[0])))
    T, P = b["trainer_pokemon"], b["player_pokemon"]
    gap = math.hypot(T[0] - P[0], T[2] - P[2])
    facts["pokemon_gap"] = round(gap, 2)
    if gap <= W:
        bad.append("the two Pokemon markers are %.2f apart: their hitboxes (%.2f wide) overlap" % (gap, W))

    # who can stand where: a walk from the building's route end
    stand = (sx, sy + 1, sz)
    reach_cells = walk(a, tuple(doc["entry"]["route_end"]), bounds, bbounds)
    facts["walkable_cells"] = len(reach_cells)
    ef = tuple(doc["entry"]["floor"])
    if ef not in reach_cells:
        bad.append("entry.floor %s cannot be reached on foot from entry.route_end %s"
                   % (list(ef), doc["entry"]["route_end"]))
    if stand in reach_cells:
        bad.append("a player can walk onto the leader's own stand %s: the dais must not be climbable" % list(stand))
    d_entry = dist3(ef, stand)
    facts["approach"] = round(d_entry, 1)
    if d_entry <= reach:
        bad.append("entry.floor is %.1f from the leader, inside forceBattleMaxDistance + 1 = %g: the battle could "
                   "start before the player is in the hall" % (d_entry, reach))
    # Battle Positions' set is valid when BOTH Pokemon blocks are found (PositionBlockFinder$PositionBlockSet.isValid);
    # the two stands are optional (a stand not found skips that teleport), so their coverage is reported, not gated.
    # A battle starts from any cell within forceBattleMaxDistance of the leader (on sight, or by interacting).
    band = rct["forceBattleMaxDistance"] - rct["forceBattleLookTicks"] * SPRINT_PER_TICK
    facts["sprint_in_look_ticks_reaches"] = round(band, 2)
    start = [c for c in reach_cells if dist3(c, stand) <= rct["forceBattleMaxDistance"] and sight(a, stand, c)]
    facts["battle_start_cells"] = len(start)
    if not start:
        bad.append("no cell a player can stand on is within forceBattleMaxDistance of the leader")
    miss, first = {k: 0 for k in MARKERS}, {}
    for c in start:
        for k in MARKERS:
            m = b[k]
            if abs(m[0] - c[0]) <= bp["h"] and abs(m[2] - c[2]) <= bp["h"] and abs(m[1] - c[1]) <= bp["v"]:
                continue
            miss[k] += 1
            first.setdefault(k, c)
    facts["markers_found_from"] = {k: "%d of %d" % (len(start) - v, len(start)) for k, v in miss.items()}
    for k in ("trainer_pokemon", "player_pokemon"):
        if miss[k]:
            bad.append("battle.%s is out of Battle Positions' search (%d across, %d up or down) from %d of %d cell(s) "
                       "a battle can start from, first %s: the set is then invalid and the mod places nobody"
                       % (k, bp["h"], bp["v"], miss[k], len(start), list(first[k])))

    # light
    lit = light_map(a, bounds)
    dark = [c for c in reach_cells if inside(c, bounds) and lit.get(c, 0) < MIN_LIGHT]
    levels = sorted(lit.get(c, 0) for c in reach_cells if inside(c, bounds))
    facts["light"] = {"cells": len(levels), "min": levels[0] if levels else None,
                      "median": levels[len(levels) // 2] if levels else None,
                      "under_8": sum(1 for v in levels if v < 8)}
    if dark:
        bad.append("%d standable cell(s) in the arena at block light 0, first %s" % (len(dark), list(dark[0])))

    # Challenge mode: a boss outside the one-leader rollout keeps a second spawner, which must stand in the arena
    cm = load(ROOT / "data" / "challenge_mode.json")
    roll = (cm.get("single_leader") or {}).get("rollout") or []
    boss = cm["bosses"].get(lead["id"])
    if boss and roll != "all" and lead["id"] not in roll:
        at = tuple(boss["spawner"]["at"])
        if not inside(at, bounds):
            bad.append("%s is not in single_leader.rollout, so its Challenge spawner bosses.%s.spawner.at %s must "
                       "move into the arena with it, and challenge_spawner.old_at name the one to take out"
                       % (lead["id"], lead["id"], list(at)))
        if not (doc.get("challenge_spawner") or {}).get("old_at"):
            bad.append("%s keeps a second spawner: challenge_spawner.old_at must name the old one" % lead["id"])
    facts["one_leader"] = lead["id"] in roll or roll == "all"
    return bad, facts


def sight(a, s, c, eye=1.62, step=0.25):
    """Eye to eye, leader at feet cell s and player at feet cell c, through open cells only: the line rctmod's
    battle on sight needs, and that an interaction needs too (a player cannot click through rock). Sampled every
    `step` blocks; a partial block (a wall, a stair) counts as blocking, which is the strict side."""
    p0 = (s[0] + 0.5, s[1] + eye, s[2] + 0.5)
    p1 = (c[0] + 0.5, c[1] + eye, c[2] + 0.5)
    d = dist3(p0, p1)
    n = max(1, int(d / step))
    for i in range(1, n):
        t = i / float(n)
        q = (int(math.floor(p0[0] + (p1[0] - p0[0]) * t)), int(math.floor(p0[1] + (p1[1] - p0[1]) * t)),
             int(math.floor(p0[2] + (p1[2] - p0[2]) * t)))
        if not is_open(a.at(*q)):
            return False
    return True


def dist3(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def walk(a, start, bounds, bbounds):
    """Every feet cell a player reaches from `start`: walk, step or jump up one, fall any distance. Generous on
    purpose (it answers 'can a player get here', where more is the safe side). Inside the arena's bounds and the
    building's, one cell round each."""
    boxes = [bounds] + ([bbounds] if bbounds else [])
    lo = [min(b[i] for b in boxes) - 1 for i in range(3)]
    hi = [max(b[i + 3] for b in boxes) + 1 for i in range(3)]

    def ok(c):
        return all(lo[i] <= c[i] <= hi[i] for i in range(3))

    def body(c):
        x, y, z = c
        return is_open(a.at(x, y, z)) and is_open(a.at(x, y + 1, z))

    def floor(c):
        x, y, z = c
        return not is_open(a.at(x, y - 1, z))

    def settle(c):
        x, y, z = c
        while y > lo[1] and body((x, y, z)) and not floor((x, y, z)):
            y -= 1
        return (x, y, z) if body((x, y, z)) and floor((x, y, z)) else None

    s = settle(start)
    if s is None:
        return set()
    seen, q = {s}, deque([s])
    while q:
        x, y, z = q.popleft()
        for dx, dz in DIRS.values():
            for dy in (1, 0):
                n = (x + dx, y + dy, z + dz)
                if not ok(n):
                    continue
                if dy == 1 and not is_open(a.at(x, y + 2, z)):
                    continue
                if body(n):
                    t = settle(n)
                    if t and t not in seen:
                        seen.add(t)
                        q.append(t)
                    break
    return seen


def light_map(a, bounds):
    """Block light from every light source the arena writes, spread through open cells, 1 lost per step."""
    lit, q = {}, deque()
    for c, s in a.cells.items():
        v = LIGHT.get(block_name(s))
        if v and ("lit=false" not in s):
            lit[c] = max(lit.get(c, 0), v)
            q.append(c)
    x0, y0, z0, x1, y1, z1 = bounds
    while q:
        c = q.popleft()
        v = lit[c] - 1
        if v <= 0:
            continue
        x, y, z = c
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + d[0], y + d[1], z + d[2])
            if not (x0 - 8 <= n[0] <= x1 + 8 and y0 - 8 <= n[1] <= y1 + 8 and z0 - 8 <= n[2] <= z1 + 8):
                continue
            if not is_open(a.at(*n)):
                continue
            if lit.get(n, 0) < v:
                lit[n] = v
                q.append(n)
    return lit


# ------------------------------------------------------------------------------------------------ the move
def old_seat_restore(doc, old):
    """(floor, under) to put back where the old spawner and its redstone stood: the commonest of the building
    model's four neighbours at each height (tools/gym_buildings.py build_one), or the record's own
    old_seat_restore for a template seat (gym 2)."""
    r = doc.get("old_seat_restore")
    at_b, _bb, _m, _d = building_model(doc["gym"])
    if at_b is None:
        if not (r and r.get("floor") and r.get("under")):
            raise ArenaError("%s: a template seat needs old_seat_restore {floor, under}" % doc["id"])
        return r["floor"], r["under"]
    x, y, z = old
    out = []
    for dy in (0, -1):
        cand = [at_b(x + dx, y + dy, z + dz) for dx, dz in DIRS.values()]
        cand = [c for c in cand if block_name(c) not in (SPAWNER, REDSTONE)]
        solid = [c for c in cand if not is_open(c)]
        # a seat in a deck can hang its redstone block in open air (gym 5's watch floor): every neighbour at that
        # height is open, and the building model's own open cell is what belongs there, never a guessed solid
        cand = solid or cand
        if not cand:
            raise ArenaError("%s: nothing beside the old seat at y%d to restore it from" % (doc["id"], y + dy))
        out.append(max(set(cand), key=cand.count))
    if r and (r.get("floor"), r.get("under")) != tuple(out):
        raise ArenaError("%s: old_seat_restore %s disagrees with the building model's %s" % (doc["id"], r, out))
    return out[0], out[1]


def challenge_id(up):
    cm = load(ROOT / "data" / "challenge_mode.json")
    return up + cm.get("id_suffix", "_challenge")


def seat_lines(doc, reach):
    """The move, once per apply, after the build: the new spawner set in the dais, the old cell back to its floor.
    Every line first tests that the OLD cell still holds a spawner, so a re-run changes nothing; the old cell is
    restored only once the new spawner stands, so the leader is never left with none. Never with a player within
    reach of either cell (no battle can start with the old leader or the new one). This is
    tools/challenge_mode.py move_lines' shape, for a gym's own seat."""
    lead = doc["leader"]
    old = old_seat(doc)
    ox, oy, oz = old
    nx, ny, nz = lead["seat"]
    floor, under = old_seat_restore(doc, old)
    r = "%g" % reach
    # the arena stands (its trainer Pokemon block is there): R16G also runs this, straight after the building, and on
    # a world whose arena was never built it must not set a spawner into the rock
    tx, ty, tz = doc["battle"]["trainer_pokemon"]
    has_old = "if block %d %d %d %s if block %d %d %d %s" % (tx, ty, tz, MARKERS["trainer_pokemon"], ox, oy, oz, SPAWNER)
    guard = ("positioned %d.5 %d %d.5 unless entity @a[distance=..%s] positioned %d.5 %d %d.5 unless entity "
             "@a[distance=..%s]" % (ox, oy, oz, r, nx, ny, nz, r))
    new_ok = "if block %d %d %d %s" % (nx, ny, nz, SPAWNER)
    lines = ["# %s: %s's spawner moves from the building (%d, %d, %d) to the arena's dais (%d, %d, %d) "
             "(data/gym_arenas/%s.json leader.seat). Run by reapply step R16GA after the arena is built"
             % (doc["id"], lead["id"], ox, oy, oz, nx, ny, nz, doc["id"]),
             "execute %s %s unless block %d %d %d %s run setblock %d %d %d %s"
             % (has_old, guard, nx, ny - 1, nz, REDSTONE, nx, ny - 1, nz, REDSTONE),
             'execute %s %s unless block %d %d %d %s run setblock %d %d %d %s{TrainerIds:["%s"]}'
             % (has_old, guard, nx, ny, nz, SPAWNER, nx, ny, nz, SPAWNER, lead["id"]),
             "execute %s %s %s run setblock %d %d %d %s" % (has_old, new_ok, guard, ox, oy - 1, oz, under),
             "execute %s %s %s run setblock %d %d %d %s" % (has_old, new_ok, guard, ox, oy, oz, floor),
             "# neither cell holds one (a world whose building step did not run this time): the leader still gets his",
             "execute if block %d %d %d %s unless block %d %d %d %s unless block %d %d %d %s run setblock %d %d %d %s"
             % (tx, ty, tz, MARKERS["trainer_pokemon"], ox, oy, oz, SPAWNER, nx, ny, nz, SPAWNER, nx, ny - 1, nz,
                REDSTONE),
             'execute if block %d %d %d %s unless block %d %d %d %s unless block %d %d %d %s run setblock %d %d %d '
             '%s{TrainerIds:["%s"]}' % (tx, ty, tz, MARKERS["trainer_pokemon"], ox, oy, oz, SPAWNER, nx, ny, nz,
                                        SPAWNER, nx, ny, nz, SPAWNER, lead["id"])]
    cs = doc.get("challenge_spawner") or {}
    if cs.get("old_at"):
        cx, cy, cz = cs["old_at"]
        cf, cu = cs["old_restore"]["floor"], cs["old_restore"]["under"]
        has_c = "if block %d %d %d %s" % (cx, cy, cz, SPAWNER)
        lines += ["# the Challenge spawner the trainers cycle set at the old seat (data/challenge_mode.json moved it "
                  "into the arena): out, its cell back to its floor",
                  "execute %s %s run setblock %d %d %d %s" % (has_c, guard, cx, cy - 1, cz, cu),
                  "execute %s %s run setblock %d %d %d %s" % (has_c, guard, cx, cy, cz, cf)]
    return lines


def old_seat(doc):
    """Where the leader's spawner stands before the move: the building's leader.spawner, or Misty's template one."""
    b = building_doc(doc["gym"])
    if b:
        return tuple(b["leader"]["spawner"])
    i = interior_doc(doc["gym"])
    if i and (i.get("leader") or {}).get("expect_spawner_at"):
        return tuple(i["leader"]["expect_spawner_at"])
    raise ArenaError("%s: no old seat in data/gym_buildings or data/gym_interiors.json" % doc["id"])


def old_leader_kills(doc):
    """Selector bodies for the leader standing anywhere in the building (both ids, never in a battle): the arena's
    seat is outside the building's bounds, so the new leader is never in them."""
    up = doc["leader"]["id"]
    b = building_doc(doc["gym"])
    if b:
        x0, y0, z0, x1, y1, z1 = norm(b["bounds"])
    else:
        x0, y0, z0, x1, y1, z1 = norm(interior_doc(doc["gym"])["shell"]["expect_box"])
    vol = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (x0, y0, z0, x1 - x0, y1 - y0, z1 - z0)
    return [('type=rctmod:trainer,%s,nbt={TrainerId:"%s",InBattle:0b}' % (vol, i)) for i in (up, challenge_id(up))], \
        (x0, z0, x1, z1)


def verify_probes(doc):
    """[(what, x, y, z, block or None for 'not a spawner')]: what the world must hold after R16GA."""
    lead, b = doc["leader"], doc["battle"]
    sx, sy, sz = lead["seat"]
    ox, oy, oz = old_seat(doc)
    out = [("the leader's spawner in the dais", sx, sy, sz, SPAWNER),
           ("its redstone", sx, sy - 1, sz, REDSTONE),
           ("air over the seat", sx, sy + 1, sz, "minecraft:air")]
    for k, block in MARKERS.items():
        out.append(("battle.%s" % k, b[k][0], b[k][1], b[k][2], block))
    out.append(("no spawner left at the old seat", ox, oy, oz, None))
    for p in doc.get("probes") or []:
        out.append((p["what"], p["at"][0], p["at"][1], p["at"][2], p["block"]))
    return out


# ------------------------------------------------------------------------------------------------- the pack
def write_fn(funcs, name, lines, loaded_by=None):
    import function_limits
    if loaded_by:
        cmds = ["# chunks-loaded-by: %s" % loaded_by] + function_limits.split_fills(lines)
    else:
        cmds = function_limits.ensure_loaded(lines)
    refused = function_limits.check_lines(cmds, name)
    if refused:
        raise ArenaError("%s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:3]))
    p = funcs / ("%s.mcfunction" % name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(cmds) + "\n", encoding="utf-8")
    return cmds


def reach():
    return rct_config()["forceBattleMaxDistance"] + 1


def build_pack(out, recs, G):
    import chunk_look
    funcs = Path(out) / "data" / NS / "function" / FOLDER
    if Path(out).exists():
        shutil.rmtree(out)
    funcs.mkdir(parents=True)
    (Path(out) / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                           "Cobblers: the gym arenas below the gym buildings (tools/gym_arenas.py)"}},
                                           indent=2) + "\n", encoding="utf-8")
    done, verify_lines = [], ["# every gym arena's probes: a line in chat for each that fails (tools/gym_arenas.py)"]
    for _p, doc in recs:
        a, build_ops, problems, _f = build(doc, G)
        if problems:
            raise ArenaError("%s:\n  %s" % (doc["id"], "\n  ".join(problems)))
        write_fn(funcs, doc["id"], build_ops)
        write_fn(funcs, doc["id"] + "_seat", seat_lines(doc, reach()))
        kills, box = old_leader_kills(doc)
        sw = chunk_look.sweep("%s:%s/%s_old_leader" % (NS, FOLDER, doc["id"]), box, kills,
                              "gym_arena_%s" % doc["id"], note="tools/gym_arenas.py")
        for path, lines in chunk_look.files(sw).items():
            p = Path(out) / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        for what, x, y, z, block in verify_probes(doc):
            test = ("if block %d %d %d %s" % (x, y, z, SPAWNER)) if block is None else \
                ("unless block %d %d %d %s" % (x, y, z, block))
            verify_lines.append('execute %s run tellraw @a {"text":"gym arena %s: %s at %d %d %d is wrong",'
                                '"color":"red"}' % (test, doc["id"], what.replace('"', "'"), x, y, z))
        verify_lines.append('tellraw @a {"text":"gym arena %s: %d probes checked","color":"gray"}'
                            % (doc["id"], len(verify_probes(doc))))
        done.append(doc["id"])
    write_fn(funcs, "verify", verify_lines)
    (funcs / "index.txt").write_text("\n".join(done) + "\n", encoding="utf-8")
    return done


def steps():
    """tools/reapply.py actions for R16GA: per arena, the build, the seat move, the old leader swept out of the
    building (tools/chunk_look.py sweep, its own forceload and wait), then the read-back."""
    import chunk_look
    out = []
    for _p, doc in records():
        base = "%s:%s/%s_old_leader" % (NS, FOLDER, doc["id"])
        out += [("fn", "%s:%s/%s" % (NS, FOLDER, doc["id"])), ("fn", "%s:%s/%s_seat" % (NS, FOLDER, doc["id"])),
                ("fn", base), ("wait", chunk_look.STEP_SECONDS)]
    if out:
        # the pack's own in-world verify (tellraw per probe, for whoever watches the console), then the read-back
        out += [("fn", "%s:%s/verify" % (NS, FOLDER)), ("check", "gym_arenas")]
    return out


def hold_boxes():
    """(x0, z0, x1, z1) per arena: its bounds and its old seat, for the read-back's forceload."""
    out = []
    for _p, doc in records():
        b = norm(doc["bounds"])
        ox, _oy, oz = old_seat(doc)
        out.append((min(b[0], ox), min(b[2], oz), max(b[3], ox), max(b[5], oz)))
    return out


def verify(rc):
    """Read back from the world after R16GA (reapply check 'gym_arenas'): every probe, and no leader of this gym
    standing in its building. `rc` sends one command and returns its text. Returns the problems."""
    problems = []
    for _p, doc in records():
        for what, x, y, z, block in verify_probes(doc):
            if block is None:
                if "passed" in rc("execute if block %d %d %d %s" % (x, y, z, SPAWNER)):
                    problems.append("%s: %s (%d, %d, %d) still holds a spawner" % (doc["id"], what, x, y, z))
            elif "passed" not in rc("execute if block %d %d %d %s" % (x, y, z, block)):
                problems.append("%s: %s at (%d, %d, %d) is not %s" % (doc["id"], what, x, y, z, block))
        kills, _box = old_leader_kills(doc)
        for k in kills:
            r = rc("execute if entity @e[%s]" % k.replace(",InBattle:0b", ""))
            if "passed" in (r or ""):
                problems.append("%s: a leader still stands in the building (%s)" % (doc["id"], r.strip()))
    return problems


# ------------------------------------------------------------------------------------------------- the survey
def data_boxes(window):
    """Every six-number box in data/ (outside data/gym_arenas) whose x/z meets `window` (x0, z0, x1, z1): a sweep
    over the data, not a list of known places, so a carved space nobody remembered is still found."""
    out = []
    wx0, wz0, wx1, wz1 = window

    def visit(o, path, f):
        if isinstance(o, dict):
            for k, v in o.items():
                visit(v, path + "." + str(k), f)
        elif isinstance(o, list):
            if len(o) == 6 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o):
                x0, y0, z0, x1, y1, z1 = norm(o)
                if -64 <= y0 <= 320 and -64 <= y1 <= 320 and x0 <= wx1 and wx0 <= x1 and z0 <= wz1 and wz0 <= z1 \
                        and (x1 - x0) < 2000 and (z1 - z0) < 2000:
                    out.append((f, path, [int(x0), int(y0), int(z0), int(x1), int(y1), int(z1)]))
                return
            for i, v in enumerate(o):
                visit(v, "%s[%d]" % (path, i), f)

    for p in sorted((ROOT / "data").rglob("*.json")):
        if DATA in p.parents:
            continue
        try:
            d = load(p)
        except ValueError:
            continue
        visit(d, "", str(p.relative_to(ROOT)).replace("\\", "/"))
    return out


def survey(G=None, margin=32):
    """Per gym: where the puzzle route ends (the leader's seat now), the lot, the ground and water round it, the
    carved spaces the data records under it, and how high an arena's shell may reach with COVER natural blocks
    over it, over three horizontal envelopes."""
    import ground as ground_mod
    import numpy as np
    import bridges
    G = G or ground_mod.load()
    seats = leader_seats()
    sizes = load(SIZES)["leaders"]
    out = []
    zones = {z["id"]: z for z in load(ROOT / "data" / "spawn_suppression.json")["spawn_free_zones"]}
    for g in load(ROOT / "data" / "gym_interiors.json")["gyms"]:
        gid = g["id"]
        b = building_doc(gid)
        stub = {"gym": gid}
        lot, lot_level = lot_of(stub)
        at_b, bbounds, bmin, _bd = building_model(gid)
        if b is None:
            sh = g["shell"]["expect_box"]
            bbounds, bmin = tuple(sh), sh[1]
        lead_id = (b or {}).get("leader", {}).get("id") or g["leader"]["id"]
        seat = [s for k, s in seats.items() if s["gym"] == gid]
        seat = seat[0] if seat else None
        route_end = seat["old_seat"] or seat["seat"] if seat else None
        zone = [z for z in zones.values() if z["id"].startswith("gym_") and
                lot[0] <= (z["box"][0] + z["box"][2]) / 2 <= lot[2] + 16 and
                lot[1] - 16 <= (z["box"][1] + z["box"][3]) / 2 <= lot[3] + 16]
        zone = zone[0] if zone else None
        win = (lot[0] - margin, lot[1] - margin, lot[2] + margin, lot[3] + margin)
        cols = [(x, z) for x in range(win[0], win[2] + 1) for z in range(win[1], win[3] + 1)]
        gr = {c: G(*c) for c in cols}
        nt = {c: natural_top(c[0], c[1], G, lot, lot_level, bbounds, bmin) for c in cols}

        def cap(box):
            x0, z0, x1, z1 = box
            return min(nt[(x, z)] for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)) - COVER

        level, wet, _definite = bridges.water(G.heights, G.world, win)
        wet_n = int(np.count_nonzero(wet))
        sea_n = sum(1 for v in gr.values() if v < 62)
        carved = []
        superseded = {x["id"] for x in load(ROOT / "data" / "gym_interiors.json")["gyms"] if x.get("superseded_by")}
        for f, path, box in data_boxes(win):
            # a building's own volumes are its lowest write, already in natural_top
            if f.startswith("data/gym_buildings/"):
                continue
            x0, y0, z0, x1, y1, z1 = box
            under = [gr[(x, z)] for x in range(max(x0, win[0]), min(x1, win[2]) + 1, 2)
                     for z in range(max(z0, win[1]), min(z1, win[3]) + 1, 2)]
            if not (under and y0 < min(under) - 2):
                continue
            state = "recorded"
            m = re.match(r"\.gyms\[(\d+)\]", path)
            if f == "data/gym_interiors.json" and m:
                gi = load(ROOT / "data" / "gym_interiors.json")["gyms"][int(m.group(1))]
                if gi["id"] in superseded:
                    state = "filled back in by R16F (tools/gym_demolish.py)"
                elif gi.get("built"):
                    state = "carved and standing"
                if not path.endswith(".dig"):
                    continue
            carved.append({"file": f, "path": path, "box": box, "state": state})
        size = [v for v in sizes.values() if v["upstream"] == lead_id]
        size = size[0]["design"] if size else None
        envs = {"lot": (lot[0], lot[1], lot[2], lot[3])}
        if zone:
            zb = zone["box"]
            envs["spawn_free_zone"] = (zb[0], zb[1], zb[2], zb[3])
        envs["lot_plus_%d" % margin] = win
        env_out = {}
        for k, box in envs.items():
            c = cap(box)
            shell_top = c
            floor_max = shell_top - 2 - (int(math.ceil(size["clear_height"])) + 1) if size else None
            env_out[k] = {"box_xz": list(box), "size": [box[2] - box[0] + 1, box[3] - box[1] + 1],
                          "shell_top_max": shell_top, "floor_y_max_for_team": floor_max,
                          "descent_from_route_end": (route_end[1] + 1 - (floor_max + 1)) if (route_end and floor_max
                                                                                              is not None) else None}
        out.append({
            "gym": gid, "leader": lead_id, "building": "data/gym_buildings/%s.json" % gid if b else
            "the COBBLEVERSE template cobbleverse:misty with a carved interior (data/gym_interiors.json gym2)",
            "route_end_seat": list(route_end) if route_end else None, "seat_now": list(seat["seat"]) if seat else None,
            "lot": list(lot), "lot_level": lot_level, "building_bounds": list(bbounds) if bbounds else None,
            "building_lowest_write": bmin, "spawn_free_zone": zone["box"] if zone else None,
            "window": list(win),
            "ground": {"min": min(gr.values()), "max": max(gr.values()),
                       "median": sorted(gr.values())[len(gr) // 2],
                       "lot_min": min(gr[(x, z)] for x in range(lot[0], lot[2] + 1) for z in range(lot[1], lot[3] + 1)),
                       "lot_max": max(gr[(x, z)] for x in range(lot[0], lot[2] + 1) for z in range(lot[1], lot[3] + 1))},
            "water": {"wet_columns": wet_n, "below_sea_level_columns": sea_n,
                      "max_level": int(level.max()) if wet_n else None},
            "carved_in_data": carved,
            "team": size,
            "envelopes": env_out,
        })
    return out


def survey_markdown(rows):
    lines = ["| Gym | Route ends (seat now) | Lot (level) | Ground in window min/med/max | Water cols / below y62 |"
             " Shell top max: lot / zone / window | Floor max for team (zone) | Descent (zone) | Carved in data |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        e = r["envelopes"]
        z = e.get("spawn_free_zone") or {}
        w = [k for k in e if k.startswith("lot_plus")][0]
        lines.append("| %s | %s | %s (%s) | %d/%d/%d | %d / %d | %s / %s / %s | %s | %s | %s |" % (
            r["gym"], r["route_end_seat"], r["lot"], r["lot_level"], r["ground"]["min"], r["ground"]["median"],
            r["ground"]["max"], r["water"]["wet_columns"], r["water"]["below_sea_level_columns"],
            e["lot"]["shell_top_max"], z.get("shell_top_max"), e[w]["shell_top_max"], z.get("floor_y_max_for_team"),
            z.get("descent_from_route_end"),
            "; ".join("%s%s %s, %s" % (c["file"].replace("data/", ""), c["path"], c["box"], c["state"])
                      for c in r["carved_in_data"][:4])
            + (" (+%d)" % (len(r["carved_in_data"]) - 4) if len(r["carved_in_data"]) > 4 else "") or "none"))
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------- probes
def presence_probes():
    """{place id: [probe]} in data/world_probes.json's shape, for tools/presence_audit.py --only extra."""
    out = {}
    for _p, doc in records():
        rows = []
        for what, x, y, z, block in verify_probes(doc):
            if block is None:
                continue
            rows.append({"what": what, "block": [x, y, z, block], "expect": True})
        ox, oy, oz = old_seat(doc)
        rows.append({"what": "no spawner at the old seat", "block": [ox, oy, oz, SPAWNER], "expect": False})
        out["%s_arena" % doc["id"]] = rows
    return out


# ------------------------------------------------------------------------------------------------------- main
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "build", "survey", "probes"):
        q = sub.add_parser(name)
        q.add_argument("--gym", default=None)
        q.add_argument("--source-root", default=None)
        if name == "build":
            q.add_argument("--out", default=str(PACK))
        if name in ("survey", "probes"):
            q.add_argument("--write", action="store_true")
    a = p.parse_args(argv)
    if a.source_root:
        os.environ["COBBLERS_SOURCE_ROOT"] = a.source_root
    import ground as ground_mod
    G = ground_mod.load()
    if a.cmd == "survey":
        rows = survey(G)
        if a.write:
            dest = ROOT / "data" / "gym_arenas" / "survey.json"
            dest.write_text(json.dumps({"schema": "gym_arena_survey/1",
                                        "generated_by": "tools/gym_arenas.py survey --write (do not hand-edit)",
                                        "cover": COVER, "gyms": rows}, indent=1) + "\n", encoding="utf-8")
            print("wrote", dest.relative_to(ROOT))
        print(survey_markdown(rows))
        return 0
    if a.cmd == "probes":
        probes = presence_probes()
        if a.write:
            wp = ROOT / "data" / "world_probes.json"
            d = load(wp)
            d["places"].update(probes)
            wp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print("wrote %d place(s) into data/world_probes.json" % len(probes))
        for k, v in probes.items():
            print(k, len(v), "probes")
        return 0
    recs = records(a.gym)
    if not recs:
        raise ArenaError("data/gym_arenas holds no record; there is nothing to generate (fail closed)")
    if a.cmd == "build":
        done = build_pack(a.out, recs, G)
        print("wrote %s: %s" % (a.out, ", ".join(done)))
        return 0
    rc = 0
    for _p, doc in recs:
        _a, ops, problems, facts = build(doc, G)
        print("%s (%s): %d cells, %d commands, dais %s, approach %s, gap %s, start cells %s, light %s, cover slack %s"
              % (doc["id"], doc["leader"]["id"], facts["cells_written"], len([o for o in ops if not o.startswith("#")]),
                 facts.get("dais_height"), facts.get("approach"), facts.get("pokemon_gap"),
                 facts.get("battle_start_cells"), facts.get("light"), facts.get("cover_slack_min")))
        if facts.get("markers_found_from"):
            print("   markers found from:", facts["markers_found_from"])
        for b in problems:
            print("   PROBLEM", b)
        rc = rc or (1 if problems else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
