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

import place_donor  # noqa: E402
import place_town  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_gym_interiors"
HEALER = "cobblemon:healing_machine"
N = r"(-?\d+)"
SETBLOCK = re.compile(r"^setblock %s %s %s (\S+)" % (N, N, N))
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)(?:\s+replace\s+(\S+))?" % ((N,) * 6))

# what a player can walk through, and what carries them
PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:ladder", "minecraft:scaffolding", "minecraft:lantern",
            "minecraft:chain", "minecraft:torch", "minecraft:wall_torch"}
CLIMBABLE = {"minecraft:ladder", "minecraft:scaffolding"}
# a lantern or a chain carries nothing, but it is also not somewhere you stand: treat it as passable and unsupporting


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
    if model.name(x, y, z) in CLIMBABLE:                       # up and down the column
        for ny in (y + 1, y - 1):
            if model.standable(x, ny, z):
                out.append((x, ny, z))
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, nz = x + dx, z + dz
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
        """Can a player stand at (x, y, z)? Either the block under it is solid, or this cell is climbable."""
        return self.name(x, y, z) in CLIMBABLE or not self.passable(x, y - 1, z)

    def standable(self, x, y, z):
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
    ground = G.Ground(source_root or os.environ.get("COBBLERS_SOURCE_ROOT"))

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

        ops = parse(lines_of(gid))
        model = Model(dig, shell)
        writes = 0
        for kind, box, state, filt in ops:
            if kind == "other":
                problems.append("%s: a command this audit cannot read: %r" % (gid, filt))
                continue
            if not (inside(box, dig) or inside(box, pen) or inside(box, rooms.get("shaft", pen))):
                problems.append("%s: a write at %s is outside the dig %s, the shaft and the declared shell "
                                "penetration %s" % (gid, list(box), list(dig), list(pen)))
            nm = block_name(state)
            if nm not in allowed:
                problems.append("%s: writes %s, which data/gym_interiors.json blocks.ids does not allow" % (gid, nm))
            if nm not in gym_allowed:
                problems.append("%s: writes %s, which the gym's own `blocks` list does not allow" % (gid, nm))
            if nm in spawn_blocks:
                problems.append("%s: writes %s, a spawn condition (data/spawn_blocks.json)" % (gid, nm))
            model.apply(kind, box, state, filt)
            writes += 1
            total += 1
        if not writes:
            problems.append("%s: its function writes nothing (fail closed)" % gid)

        # rooms in the dig, and the cover over them
        for rid, box in rooms.items():
            if not (inside(box, dig) or inside(box, pen) or rid == "shaft"):
                problems.append("%s: room %s at %s is not inside the dig %s" % (gid, rid, list(box), list(dig)))
            if rid == "shaft":
                continue                                  # the shaft reaches the shell by design
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
            here = rooms_of(x, y, z)
            if not here:
                problems.append("%s: route step %d %s is in no room" % (gid, i, wp["at"]))
            elif belongs.get(wp["room"], wp["room"]) not in here:
                problems.append("%s: route step %d %s says room %s but lies in %s"
                                % (gid, i, wp["at"], wp["room"], sorted(here)))

        for t in gym["trainers"]:
            x, y, z = t["seat"]
            if not model.standable(x, y, z):
                problems.append("%s: trainer %s's seat %s is not standable" % (gid, t["id"], t["seat"]))
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
                if fall > rules["max_fall"] and model.name(nx, ly - 1, nz) != "minecraft:hay_block":
                    bad_falls += 1
                    if bad_falls <= 3:
                        problems.append("%s: stepping off %s drops %d onto %s at %s (over max_fall %d and not straw)"
                                        % (gid, [cx, cy, cz], fall, model.name(nx, ly - 1, nz), [nx, ly - 1, nz],
                                           rules["max_fall"]))
        if bad_falls > 3:
            problems.append("%s: %d more falls over max_fall not landing on straw" % (gid, bad_falls - 3))

        # zones: the suppression box and the no_build boxes
        supp = suppression.get(gym["spawn_suppression"]["record"])
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
            if rid == "shaft":
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
    p.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    a = p.parse_args(argv)
    problems, total = audit(Path(a.pack), a.source_root)
    for pr in problems:
        print("  PROBLEM", pr)
    print("gym interiors audit: %s (%d writes checked)"
          % ("CLEAN" if not problems and total else "%d PROBLEMS" % len(problems), total))
    return 1 if problems or total == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
