#!/usr/bin/env python
"""The gym interiors against the placements, the heightmap and the contracts: offline, fail-closed.

tools/gym_interiors.py writes `cobblers:gym_interiors/healers` and `cobblers:gym_interiors/<gym>` from
data/gym_interiors.json. This audit reads those written functions - the output - and checks them against data it
reads and derives on its own. It never reads the generator's report, never imports the generator, and never reads a
world.

  present     the pack exists, its index names exactly the functions data/gym_interiors.json asks for, and every
              function writes at least one block. Nothing to check is a failure
  healers     every gym in data/gym_interiors.json has `fill ... replace cobblemon:healing_machine` cover covering
              exactly the shell box this audit re-derives from data/placements.json (position, size, rotation,
              through tools/place_donor.py box()); the replacement is in the record's `blocks` list and is no spawn
              condition in data/spawn_blocks.json; and the measured healer cell, mapped through the placement's own
              rotation, lies inside that cover. No gym is missed and no fill reaches outside a shell
  blocks      every block any function writes is in data/gym_interiors.json `blocks.ids` and in the gym's own
              `blocks`, and none is a spawn condition (data/spawn_blocks.json)
  bounds      every write of a built gym lies inside that gym's `dig` box or its declared `shell_penetration`;
              nothing else touches the standing building
  rooms       every room box lies in the dig (the shaft and the penetration excepted, which reach the shell by
              design); two rooms the route does not join keep at least `rules.min_rock_between_rooms` of rock
              between them; every room's ceiling block is at least `rules.min_cover` under the heightmap's ground
              over it (tools/ground.py, rounded - the canonical heightmap, never a world)
  standing    the commands are replayed into a voxel model of the dig, and every route waypoint and every trainer
              seat is standable in it (passable at y and y+1, carried by a solid or climbable block)
  sight       contract from docs/mechanics/GYM_INTERIORS.md section 3: each trainer's forceBattleMaxDistance
              reaches no standable cell outside its own room (a doorway counts as the room it `belongs_to`).
              The sight check passes through walls, so this is measured as a ball, not a line of sight
  route       every trainer seat lies within `rules.sight_margin` + its sight distance of the route waypoint its
              `passed_at` names, so "a player must pass them" is machine checked
  falls       contract G3: stepping off any standable cell lands on something. A fall longer than `rules.max_fall`
              must land on minecraft:hay_block
  zones       contract G1: every room box lies inside the gym's data/spawn_suppression.json box in x/z.
              Contract G4: every room box lies inside a declared `no_build` box

  python tools/gym_interiors_audit.py [--pack build/datapacks/cobblers_gym_interiors]
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

import place_donor  # noqa: E402
import place_town  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_gym_interiors"
HEALER = "cobblemon:healing_machine"
N = r"(-?\d+)"
SETBLOCK = re.compile(r"^setblock %s %s %s (\S+)" % (N, N, N))
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)(?:\s+replace\s+(\S+))?" % ((N,) * 6))

# what a player can walk through, and what carries them
PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:ladder", "minecraft:scaffolding", "minecraft:lantern",
            "minecraft:chain", "minecraft:torch", "minecraft:wall_torch", "minecraft:water"}
CLIMBABLE = {"minecraft:ladder", "minecraft:scaffolding"}
WATER = {"minecraft:water"}
# a lantern or a chain carries nothing, but it is also not somewhere you stand: treat it as passable and unsupporting.
# water carries: a player in water neither falls nor needs a floor, and can swim up and down it, so a water cell is
# standable in this model and a drop that ends in water ends there.


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def parse(lines):
    """[(kind, box, state, filter)] for every write, in order. Fills keep their box; setblocks are 1x1x1."""
    out = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = SETBLOCK.match(line)
        if m:
            x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
            out.append(("setblock", (x, y, z, x, y, z), m.group(4), None))
            continue
        m = FILL.match(line)
        if m:
            g = [int(m.group(i)) for i in range(1, 7)]
            out.append(("fill", tuple(g), m.group(7), m.group(8)))
            continue
        if line.startswith(("forceload", "execute", "function", "scoreboard", "tag")):
            continue
        out.append(("other", None, None, line))
    return out


def gap(a, b):
    """Blocks of untouched rock between two inclusive boxes; 0 if they touch or overlap."""
    best = 0
    for i in (0, 1, 2):
        lo_a, hi_a, lo_b, hi_b = a[i], a[i + 3], b[i], b[i + 3]
        best = max(best, lo_b - hi_a - 1, lo_a - hi_b - 1)
    return max(best, 0)


def inside(inner, outer):
    return all(outer[i] <= inner[i] and inner[i + 3] <= outer[i + 3] for i in (0, 1, 2))


def intersect(a, b):
    """The cells two inclusive boxes share, or None. Used to ask what part of a write lands in the standing shell."""
    lo = [max(a[i], b[i]) for i in (0, 1, 2)]
    hi = [min(a[i + 3], b[i + 3]) for i in (0, 1, 2)]
    if any(lo[i] > hi[i] for i in (0, 1, 2)):
        return None
    return tuple(lo) + tuple(hi)


def inside_xz(inner, box_xz):
    x0, z0, x1, z1 = box_xz
    return x0 <= inner[0] and inner[3] <= x1 and z0 <= inner[2] and inner[5] <= z1


# ---------------------------------------------------------------------------------------------------- the model
def walk(model, start, bounds, blocked=frozenset(), limit=64):
    """Every cell a player can reach on foot from `start`, inside `bounds`, avoiding `blocked`.

    The moves are vanilla: walk level, step up one, drop to whatever is below (however far - the fall check
    above is what says a drop is survivable), and climb a ladder or scaffolding up and down. It is directed:
    a one-way chute is reachable one way and not the other, which is the point of having one."""
    x0, y0, z0, x1, y1, z1 = bounds
    seen, queue = {tuple(start)}, [tuple(start)]
    while queue:
        x, y, z = queue.pop()
        for nx, ny, nz in _steps(model, x, y, z, limit):
            c = (nx, ny, nz)
            if c in seen or c in blocked:
                continue
            if not (x0 <= nx <= x1 and y0 <= ny <= y1 and z0 <= nz <= z1):
                continue
            seen.add(c)
            queue.append(c)
    return seen


def _steps(model, x, y, z, limit):
    out = []
    here_water = model.name(x, y, z) in WATER
    if model.name(x, y, z) in CLIMBABLE or here_water:          # up and down the column, or swim up and down it
        for ny in (y + 1, y - 1):
            if not model.standable(x, ny, z):
                continue
            if ny < y and model.bubble_up(x, ny, z):
                continue        # an upward bubble column cannot be swum down: that is what makes it a one-way door
            out.append((x, ny, z))
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, nz = x + dx, z + dz
        # a flooded gap one block high: the swimming pose fits where the walking one does not, so a water cell is
        # entered from water (or from a cell whose own head is clear) without needing headroom of its own
        if model.name(nx, y, nz) in WATER and (here_water or model.passable(x, y + 1, z)):
            out.append((nx, y, nz))
        if model.standable(nx, y, nz) and model.passable(x, y + 1, z):
            out.append((nx, y, nz))
        if (model.standable(nx, y + 1, nz) and model.passable(x, y + 1, z)
                and model.passable(x, y + 2, z) and model.passable(nx, y + 2, nz)):
            out.append((nx, y + 1, nz))                        # a one-block step up
        if model.passable(nx, y, nz) and model.passable(nx, y + 1, nz) and not model.carries(nx, y, nz):
            ly = y - 1
            while ly > y - limit and model.passable(nx, ly, nz) and not model.carries(nx, ly, nz):
                ly -= 1
            if model.standable(nx, ly, nz):
                out.append((nx, ly, nz))                       # a drop
    return out


class Model:
    """A voxel replay of one gym's function. Everything in the dig starts as untouched rock; the shell above it is
    the measured floor course (solid) with its hall (air) over that. Nothing is read from a world."""

    def __init__(self, dig, shell):
        self.x0, self.y0, self.z0, self.x1, self.y1, self.z1 = dig
        self.top = max(self.y1, shell[4] if shell else self.y1)
        self.shell = shell
        self.cells = {}

    def _default(self, x, y, z):
        if y <= self.y1:
            return "minecraft:stone"                   # untouched rock under the lot
        s = self.shell
        if s and s[0] <= x <= s[3] and s[2] <= z <= s[5]:
            if y in (s[1], s[1] + 1):
                return "minecraft:stone_bricks"        # the shell's base course and its floor course (measured solid)
            return "minecraft:air"                     # the hall over the floor
        return "minecraft:air"

    def get(self, x, y, z):
        v = self.cells.get((x, y, z))
        return v if v is not None else self._default(x, y, z)

    def apply(self, kind, box, state, filt):
        x0, y0, z0, x1, y1, z1 = box
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    if filt and block_name(self.get(x, y, z)) != block_name(filt):
                        continue
                    self.cells[(x, y, z)] = state

    def name(self, x, y, z):
        return block_name(self.get(x, y, z))

    def passable(self, x, y, z):
        return self.name(x, y, z) in PASSABLE

    def carries(self, x, y, z):
        """Can a player hold this cell? The block under it is solid, or the cell is climbable, or it is water."""
        return self.name(x, y, z) in CLIMBABLE or self.name(x, y, z) in WATER or not self.passable(x, y - 1, z)

    def bubble_up(self, x, y, z, limit=48):
        """Is this cell inside an upward bubble column? Vanilla: soul sand under a column of water makes one, and a
        player in it is carried up and cannot swim down through it. Scanning down through contiguous water is how the
        column is found, so nothing here is authored: it follows from the blocks the function writes."""
        if self.name(x, y, z) not in WATER:
            return False
        ly = y
        while ly > y - limit:
            below = self.name(x, ly - 1, z)
            if below == "minecraft:soul_sand":
                return True
            if below not in WATER:
                return False
            ly -= 1
        return False

    def standable(self, x, y, z):
        if self.name(x, y, z) in WATER:
            return True                                        # swimming needs no headroom of its own
        return self.passable(x, y, z) and self.passable(x, y + 1, z) and self.carries(x, y, z)


# -------------------------------------------------------------------------------------------------------- audit
def audit(pack, source_root=None):
    problems, total = [], 0
    doc = load(ROOT / "data" / "gym_interiors.json")
    placements = load(ROOT / "data" / "placements.json")
    recs = {p["id"]: p for p in placements["placements"] if isinstance(p, dict) and p.get("id")}
    spawn_blocks = set(load(ROOT / "data" / "spawn_blocks.json")["blocks"])
    suppression = {s["id"]: s["box"] for s in load(ROOT / "data" / "spawn_suppression.json")["spawn_free_zones"]}
    allowed = set(doc["blocks"]["ids"])
    rules = doc["rules"]

    funcs = pack / "data" / "cobblers" / "function" / "gym_interiors"
    if not funcs.is_dir():
        return ["no pack at %s: nothing to check (fail closed)" % pack], 0
    index_file = funcs / "index.txt"
    if not index_file.is_file():
        return ["no %s: the pack's index is how this audit knows what should exist (fail closed)" % index_file], 0
    index = [l.strip() for l in index_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    built = [g for g in doc["gyms"] if g.get("built")]
    want = ["healers"] + [g["id"] for g in built]
    if not built:
        problems.append("data/gym_interiors.json marks no gym built: there is no interior to check (fail closed)")
    if index != want:
        problems.append("the pack index is %s but data/gym_interiors.json asks for %s" % (index, want))

    def lines_of(name):
        f = funcs / ("%s.mcfunction" % name)
        if not f.is_file():
            problems.append("no function %s" % f)
            return []
        return f.read_text(encoding="utf-8").splitlines()

    # ---- healers ------------------------------------------------------------------------------------------------
    ops = parse(lines_of("healers"))
    covers = {}
    for kind, box, state, filt in ops:
        if kind == "other":
            problems.append("healers: a command this audit cannot read: %r" % filt)
            continue
        if block_name(filt or "") != HEALER:
            problems.append("healers: a write that is not a healing-machine replacement: %s %s" % (kind, state))
            continue
        covers.setdefault(block_name(state), []).append(box)
        total += 1
    seen = set()
    for g in doc["healers"]["gyms"]:
        rec = recs.get(g["donor"])
        if rec is None:
            problems.append("healers: %s names donor %s, which data/placements.json does not have" % (g["gym"], g["donor"]))
            continue
        (sx0, sy0, sz0), (sx1, sy1, sz1) = place_donor.box(rec)
        shell = (sx0, sy0, sz0, sx1, sy1, sz1)
        boxes = covers.get(block_name(g["replacement"]), [])
        mine = [b for b in boxes if inside(b, shell)]
        stray = [b for b in boxes if not inside(b, shell)]
        if stray:
            problems.append("healers: %s writes %s outside its shell %s" % (g["gym"], stray[0], list(shell)))
        ys = set()
        for b in mine:
            if (b[0], b[2], b[3], b[5]) != (sx0, sz0, sx1, sz1):
                problems.append("healers: %s's fill %s does not span its shell's footprint %s"
                                % (g["gym"], list(b), [sx0, sz0, sx1, sz1]))
            ys.update(range(b[1], b[4] + 1))
        if ys != set(range(sy0, sy1 + 1)):
            problems.append("healers: %s's fills cover y %s, not the whole shell %d..%d (a machine outside the "
                            "covered slabs would survive)" % (g["gym"], sorted(ys)[:3] or "nothing", sy0, sy1))
        dx, dz = place_town.rotate(g["expect_at"][0], g["expect_at"][2], rec.get("rotation", "none"))
        p = rec["position"]
        hx, hy, hz = p["x"] + dx, p["y"] + g["expect_at"][1], p["z"] + dz
        if not any(b[0] <= hx <= b[3] and b[1] <= hy <= b[4] and b[2] <= hz <= b[5] for b in mine):
            problems.append("healers: %s's measured healer cell %s is not inside any of its fills"
                            % (g["gym"], [hx, hy, hz]))
        if block_name(g["replacement"]) not in allowed:
            problems.append("healers: %s's replacement %s is not in data/gym_interiors.json blocks.ids" % (g["gym"], g["replacement"]))
        if block_name(g["replacement"]) in spawn_blocks:
            problems.append("healers: %s's replacement %s is a spawn condition (data/spawn_blocks.json)" % (g["gym"], g["replacement"]))
        seen.add(g["gym"])
    for g in doc["gyms"]:
        if g["id"] not in seen:
            problems.append("healers: gym %s has no healing-machine removal; the owner's call was all eight" % g["id"])

    # ---- each built gym -----------------------------------------------------------------------------------------
    import ground as G
    ground = G.Ground(source_root or env_source_root())

    for gym in built:
        gid = gym["id"]
        rec = recs.get(gym["donor"])
        if rec is None:
            problems.append("%s: donor %s is not in data/placements.json" % (gid, gym["donor"]))
            continue
        (sx0, sy0, sz0), (sx1, sy1, sz1) = place_donor.box(rec)
        shell = (sx0, sy0, sz0, sx1, sy1, sz1)
        dig = tuple(gym["dig"])
        pen = tuple(gym["shell_penetration"])
        gym_allowed = set(gym["blocks"])
        rooms = {r["id"]: tuple(r["box"]) for r in gym["rooms"]}
        belongs = {r["id"]: r.get("belongs_to", r["id"]) for r in gym["rooms"]}
        roles = {r["id"]: r.get("role") for r in gym["rooms"]}
        shafts = {rid for rid, role in roles.items() if role == "shaft"}
        # a block that is a spawn condition may be written only where it is declared and only inside this gym's
        # spawn-free box: contract G1 is what makes it safe, and the box is the whole of the reason
        exempt = {e["id"]: e for e in gym.get("spawn_condition_blocks") or []}
        supp = suppression.get(gym["spawn_suppression"]["record"])

        # ---- the interior against the placement, not against itself -------------------------------------------
        # The entrance is the measured healer cell mapped through this placement's own rotation. Nothing in the
        # generator's output is consulted: this comes from data/placements.json and the Q1 measurements.
        rel = doc["measured"]["misty_relative" if gid == "gym2" else "small_gym_relative"]
        dx, dz = place_town.rotate(rel["healing_machine"][0], rel["healing_machine"][2], rec.get("rotation", "none"))
        pos = rec["position"]
        want_entrance = [pos["x"] + dx, pos["y"] + rel["healing_machine"][1], pos["z"] + dz]
        if list(gym["entrance"]) != want_entrance:
            problems.append("%s: its entrance is %s but the measured healer cell, mapped through this placement's "
                            "rotation, is %s; the entrance is the only interior cell of the shell we know"
                            % (gid, list(gym["entrance"]), want_entrance))
        if [gym["shell"]["expect_floor_course_y"], gym["shell"]["expect_stand_y"]] != \
                [sy0 + rel["floor_course_y"], sy0 + rel["interior_floor_y"]]:
            problems.append("%s: its recorded floor course and standing level are %s but the placement and the "
                            "measured template give %s" % (gid, [gym["shell"]["expect_floor_course_y"],
                            gym["shell"]["expect_stand_y"]], [sy0 + rel["floor_course_y"], sy0 + rel["interior_floor_y"]]))
        # The dig is under the lot and below the building: a carve that reaches the shell's own courses would be
        # cutting the placed template, which only the declared penetration may do.
        if dig[4] >= sy0:
            problems.append("%s: its dig reaches y%d, at or above the shell's lowest course y%d; the carve must be "
                            "wholly below the standing building" % (gid, dig[4], sy0))
        if supp is not None and not inside_xz(dig, supp):
            problems.append("%s: its dig %s leaves the spawn-free box %s in x/z (contract G1)" % (gid, list(dig), supp))
        # The penetration is one column, at the entrance, and no higher than the shell.
        if (pen[0], pen[2]) != (pen[3], pen[5]) or (pen[0], pen[2]) != (want_entrance[0], want_entrance[2]):
            problems.append("%s: its shell penetration %s is not a single column at the entrance %s"
                            % (gid, list(pen), want_entrance))
        if pen[1] < sy0 or pen[4] > want_entrance[1]:
            problems.append("%s: its shell penetration runs y%d..%d, outside the shell's base course y%d and the "
                            "entrance cell y%d" % (gid, pen[1], pen[4], sy0, want_entrance[1]))

        ops = parse(lines_of(gid))
        model = Model(dig, shell)
        writes = 0
        for kind, box, state, filt in ops:
            if kind == "other":
                problems.append("%s: a command this audit cannot read: %r" % (gid, filt))
                continue
            # anything that reaches the standing building may only be the declared penetration
            hit = intersect(box, shell)
            if hit and not inside(hit, pen):
                problems.append("%s: a write at %s puts %s inside the placed template's own box %s, outside the "
                                "declared shell penetration %s" % (gid, list(box), list(hit), list(shell), list(pen)))
            if not (inside(box, dig) or inside(box, pen)
                    or any(inside(box, rooms[s]) for s in shafts)):
                problems.append("%s: a write at %s is outside the dig %s, the shaft and the declared shell "
                                "penetration %s" % (gid, list(box), list(dig), list(pen)))
            nm = block_name(state)
            if nm not in allowed:
                problems.append("%s: writes %s, which data/gym_interiors.json blocks.ids does not allow" % (gid, nm))
            if nm not in gym_allowed:
                problems.append("%s: writes %s, which the gym's own `blocks` list does not allow" % (gid, nm))
            if nm in spawn_blocks:
                if nm not in exempt:
                    problems.append("%s: writes %s, a spawn condition (data/spawn_blocks.json), and the gym's "
                                    "`spawn_condition_blocks` does not declare it" % (gid, nm))
                elif supp is None or not inside_xz(box, supp):
                    problems.append("%s: writes the spawn condition %s at %s, which is not inside the gym's "
                                    "spawn-free box %s (contract G1 is the only thing that makes it safe)"
                                    % (gid, nm, list(box), supp))
            model.apply(kind, box, state, filt)
            writes += 1
            total += 1
        if not writes:
            problems.append("%s: its function writes nothing (fail closed)" % gid)

        # rooms in the dig, and the cover over them
        for rid, box in rooms.items():
            if not (inside(box, dig) or inside(box, pen) or rid in shafts):
                problems.append("%s: room %s at %s is not inside the dig %s" % (gid, rid, list(box), list(dig)))
            if rid in shafts:
                continue                                  # a shaft reaches the shell by design
            ceiling = box[4] + 1
            for x in range(box[0], box[3] + 1):
                for z in range(box[2], box[5] + 1):
                    g_here = int(round(ground(x, z)))
                    if ceiling + rules["min_cover"] > g_here:
                        problems.append("%s: room %s's ceiling at y%d has only %d blocks of cover at %d,%d "
                                        "(ground y%d, wanted %d)" % (gid, rid, ceiling, g_here - ceiling, x, z,
                                                                     g_here, rules["min_cover"]))
                        break
                else:
                    continue
                break

        # rock between rooms the route does not join
        joined = {tuple(sorted((a["room"], b["room"]))) for a, b in zip(gym["route"], gym["route"][1:])}
        joined |= {tuple(sorted((rid, belongs[rid]))) for rid in rooms}
        ids = sorted(rooms)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if tuple(sorted((a, b))) in joined:
                    continue
                d = gap(rooms[a], rooms[b])
                if d < rules["min_rock_between_rooms"]:
                    problems.append("%s: rooms %s and %s are %d blocks apart and the route does not join them "
                                    "(wanted %d of rock)" % (gid, a, b, d, rules["min_rock_between_rooms"]))

        # what a cell belongs to. Room boxes may overlap (the shaft stands inside the cutting floor), so this is a
        # set: a cell is "outside room R" only when R is not one of the rooms whose box holds it.
        def rooms_of(x, y, z):
            return {belongs[rid] for rid, bx in rooms.items()
                    if bx[0] <= x <= bx[3] and bx[1] <= y <= bx[4] and bx[2] <= z <= bx[5]}

        # standing: the route and the seats
        for i, wp in enumerate(gym["route"]):
            x, y, z = wp["at"]
            if not model.standable(x, y, z):
                problems.append("%s: route step %d %s is not standable: %s at the feet, %s at the head, %s under"
                                % (gid, i, wp["at"], model.name(x, y, z), model.name(x, y + 1, z), model.name(x, y - 1, z)))
            wet = model.name(x, y, z) in WATER
            if (wp.get("posture") == "swim") != wet:
                problems.append("%s: route step %d %s says posture %r but the cell is %s"
                                % (gid, i, wp["at"], wp.get("posture"), model.name(x, y, z)))
            here = rooms_of(x, y, z)
            if not here:
                problems.append("%s: route step %d %s is in no room" % (gid, i, wp["at"]))
            elif belongs.get(wp["room"], wp["room"]) not in here:
                problems.append("%s: route step %d %s says room %s but lies in %s"
                                % (gid, i, wp["at"], wp["room"], sorted(here)))

        # contract G2: no gym route asks for more than a few seconds under water. A run is the distance walked
        # between consecutive waypoints that are both in water; `rules.max_submerged_run` is its ceiling in blocks
        def under(at):
            """Head under water: the cell and the cell over it are both water. A swimmer at the surface is not."""
            x, y, z = at
            return model.name(x, y, z) in WATER and model.name(x, y + 1, z) in WATER

        run = 0.0
        for a, b in zip(gym["route"], gym["route"][1:]):
            run = run + math.dist(a["at"], b["at"]) if (under(a["at"]) and under(b["at"])) else 0.0
            if run > rules.get("max_submerged_run", 1e9):
                problems.append("%s: the route swims %.0f blocks under water without a surface by step %s "
                                "(contract G2, max_submerged_run %s)"
                                % (gid, run, b["at"], rules.get("max_submerged_run")))
                break

        for t in gym["trainers"]:
            x, y, z = t["seat"]
            if not model.standable(x, y, z):
                problems.append("%s: trainer %s's seat %s is not standable" % (gid, t["id"], t["seat"]))
            if model.name(x, y, z) in WATER:
                problems.append("%s: trainer %s's seat %s is in water; a placed trainer stands on the floor"
                                % (gid, t["id"], t["seat"]))
            if belongs.get(t["room"], t["room"]) not in rooms_of(x, y, z):
                problems.append("%s: trainer %s says room %s but its seat lies in %s"
                                % (gid, t["id"], t["room"], sorted(rooms_of(x, y, z))))
            # the sight rule: no standable cell outside its own room within reach
            r = float(t["sight_distance"])
            rr = int(math.ceil(r)) + 1
            worst = None
            for dx in range(-rr, rr + 1):
                for dy in range(-rr, rr + 1):
                    for dz in range(-rr, rr + 1):
                        cx, cy, cz = x + dx, y + dy, z + dz
                        d = math.sqrt((cx + 0.5 - (x + 0.5)) ** 2 + (cy - y) ** 2 + (cz + 0.5 - (z + 0.5)) ** 2)
                        if d > r:
                            continue
                        if not model.standable(cx, cy, cz):
                            continue
                        rm = rooms_of(cx, cy, cz)
                        if belongs.get(t["room"], t["room"]) not in rm:
                            if worst is None or d < worst[0]:
                                worst = (d, (cx, cy, cz), sorted(rm))
            if worst:
                problems.append("%s: trainer %s (sight %.1f) reaches a standable cell %s in %s, %.2f away; the sight "
                                "check passes through walls" % (gid, t["id"], r, list(worst[1]), worst[2] or "no room", worst[0]))
            # the route passes it
            idx = t["passed_at"]
            if not (0 <= idx < len(gym["route"])):
                problems.append("%s: trainer %s's passed_at %d is not a route step" % (gid, t["id"], idx))
            else:
                wx, wy, wz = gym["route"][idx]["at"]
                d = math.dist((wx, wy, wz), (x, y, z))
                if d > r + rules["sight_margin"]:
                    problems.append("%s: trainer %s sits %.1f from the route step it claims to guard (reach %.1f)"
                                    % (gid, t["id"], d, r))

        # the route is walkable, step by step, and no trainer on it can be walked round
        bounds = (min(dig[0], shell[0]), dig[1], min(dig[2], shell[2]),
                  max(dig[3], shell[3]), max(dig[4], shell[4]), max(dig[5], shell[5]))
        steps = [tuple(w["at"]) for w in gym["route"]]
        for i, (a, b) in enumerate(zip(steps, steps[1:])):
            if b not in walk(model, a, bounds):
                problems.append("%s: route step %d %s cannot be walked to from step %d %s: the way is broken"
                                % (gid, i + 1, list(b), i, list(a)))
        for t in gym["trainers"]:
            sx, sy, sz = t["seat"]
            r = float(t["sight_distance"])
            ball = {c for c in cell_range(dig)
                    if math.dist((c[0] + 0.5, c[1], c[2] + 0.5), (sx + 0.5, sy, sz + 0.5)) <= r}
            after = [s for j, s in enumerate(steps) if j > t["passed_at"] and s not in ball]
            if not after:
                problems.append("%s: trainer %s is the last thing on the route, so nothing is behind it" % (gid, t["id"]))
                continue
            if after[0] in walk(model, steps[0], bounds, blocked=ball):
                problems.append("%s: trainer %s can be walked round: %s is reachable from the route's start with "
                                "every cell in its %.1f-block reach closed off (why_unavoidable is not true)"
                                % (gid, t["id"], list(after[0]), r))

        # falls: stepping off a standable cell
        bad_falls = 0
        for (cx, cy, cz) in sorted(set(cell_range(dig))):
            if not model.standable(cx, cy, cz):
                continue
            for ddx, ddz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = cx + ddx, cz + ddz
                if not (model.passable(nx, cy, nz) and model.passable(nx, cy + 1, nz)):
                    continue
                if model.carries(nx, cy, nz):
                    continue
                ly = cy - 1
                while ly > dig[1] and model.passable(nx, ly, nz) and not model.carries(nx, ly, nz):
                    ly -= 1
                fall = cy - ly
                soft = (model.name(nx, ly - 1, nz) == "minecraft:hay_block"
                        or model.name(nx, ly, nz) in WATER or model.name(nx, ly - 1, nz) in WATER)
                if fall > rules["max_fall"] and not soft:
                    bad_falls += 1
                    if bad_falls <= 3:
                        problems.append("%s: stepping off %s drops %d onto %s at %s (over max_fall %d and not straw)"
                                        % (gid, [cx, cy, cz], fall, model.name(nx, ly - 1, nz), [nx, ly - 1, nz],
                                           rules["max_fall"]))
        if bad_falls > 3:
            problems.append("%s: %d more falls over max_fall not landing on straw" % (gid, bad_falls - 3))

        # zones: the suppression box and the no_build boxes
        if supp is None:
            problems.append("%s: data/spawn_suppression.json has no zone %s" % (gid, gym["spawn_suppression"]["record"]))
        else:
            if supp != gym["spawn_suppression"]["box"]:
                problems.append("%s: data/spawn_suppression.json %s is %s but the record says %s"
                                % (gid, gym["spawn_suppression"]["record"], supp, gym["spawn_suppression"]["box"]))
            for rid, box in rooms.items():
                if not inside_xz(box, supp):
                    problems.append("%s: room %s at %s leaves the spawn-free box %s in x/z (contract G1)"
                                    % (gid, rid, list(box), supp))
        nb = [tuple(b["box"]) for b in gym["no_build"]]
        for rid, box in rooms.items():
            if rid in shafts:
                continue
            if not any(inside(box, b) for b in nb):
                problems.append("%s: room %s is in no no_build box (contract G4)" % (gid, rid))

    return problems, total


def cell_range(box):
    x0, y0, z0, x1, y1, z1 = box
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                yield (x, y, z)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("--source-root", default=env_source_root())
    a = p.parse_args(argv)
    problems, total = audit(Path(a.pack), a.source_root)
    for pr in problems:
        print("  PROBLEM", pr)
    print("gym interiors audit: %s (%d writes checked)"
          % ("CLEAN" if not problems and total else "%d PROBLEMS" % len(problems), total))
    return 1 if problems or total == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
