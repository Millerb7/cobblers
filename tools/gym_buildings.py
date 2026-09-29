#!/usr/bin/env python
"""The authored gym buildings: one hall per gym, with its puzzle inside it, from data/gym_buildings/<gym>.json.

The owner's call, 2026-09-29 (docs/world-building/GYM_BUILDINGS_BRIEF.md): "id rather have a large gym building
with a puzzle inside than whatever that was". The COBBLEVERSE donor shell at gyms 1, 3, 4, 5 and 7 is taken down
by tools/gym_demolish.py and replaced by a building we author. Gym 2, Misty's, is kept exactly as built and is
not touched by either tool.

  python tools/gym_buildings.py report [--gym gym1] [--source-root <root>]
  python tools/gym_buildings.py build  [--out build/datapacks/cobblers_gym_buildings] [--source-root <root>]

ONE FILE PER GYM, in data/gym_buildings/. Four more buildings are written by four more agents; a directory keeps
them out of each other's way. Nothing in this tool is per-gym: it reads every data/gym_buildings/*.json and emits
`cobblers:gym_buildings/<id>` for each. An author writes data only. The record's fields and the op vocabulary are
documented in docs/world-building/GYM_BUILDINGS.md; that document, not this docstring, is the contract.

Where the ground comes from: data/placements.json's own town plan. A gym lot is a levelled pad - the town prep
cuts and fills it to `level` (tools/place_town.py: "a levelled lot is cut and filled to its level by the prep, so
that is its ground") - so a building on a levelled lot stands on that number, which is measured plan data, not a
world read. A record may instead declare `"ground": {"kind": "heightmap"}`, and then every column's ground comes
from tools/ground.py, rounded. Neither path reads a world save (the ground rule, tests/test_ground_rule.py).

What this tool refuses to write, and why each check is here rather than in an audit (the audit is written by
another agent - CLAUDE.md principle 16 - and replays the emitted text independently):

  block list      every block a record writes must be in its own `blocks` list, so a stray block state cannot
                  arrive unnoticed; and `cobblemon:healing_machine` is refused outright (the brief: no healing
                  machine in any gym)
  bounds          every write lands inside the record's declared `bounds`, and `bounds` inside the lot rect from
                  data/placements.json, so a gym building cannot spill off its own levelled pad onto a street
  support         a block that vanilla would pop - a ladder with nothing behind it, a lantern hanging from air,
                  a falling block over a hole - fails the build. `setblock` does not check support and nothing
                  else reports it: 31 lanterns stood in mid air across the five interiors this work replaces
  spawner         exactly one rctmod:trainer_spawner, powered from below (EXP-013 E2) and with two air cells
                  over it, or the leader never spawns
  commands        tools/function_limits.py: fills split under the /fill limit, and every write inside a chunk
                  the function force-loads for its whole run
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import ground as ground_mod  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_gym_buildings"
FUNCS = PACK / "data" / "cobblers" / "function" / "gym_buildings"
REPORT = ROOT / "derived" / "gym_buildings"
DATA = ROOT / "data" / "gym_buildings"
PLACEMENTS = ROOT / "data" / "placements.json"
HEALER = "cobblemon:healing_machine"
SPAWNER = "rctmod:trainer_spawner"
SCHEMA = "gym_building/1"

# The ground rule (tools/ground_rule.py): nothing here reads a world at all.
WORLD_READS = set()

OPS = ("fill", "setblock", "scatter", "columns", "gable_roof", "comment")


# ------------------------------------------------------------------------------------------------------ loading
def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def records(only=None):
    """Every data/gym_buildings/*.json, by id, in file order."""
    out = []
    for p in sorted(DATA.glob("*.json")):
        doc = load(p)
        if doc.get("schema") != SCHEMA:
            raise SystemExit("%s: schema is %r, expected %r" % (p.name, doc.get("schema"), SCHEMA))
        if doc["id"] != p.stem:
            raise SystemExit("%s: record id %r does not match its file name" % (p.name, doc["id"]))
        if only and doc["id"] != only:
            continue
        out.append((p, doc))
    if only and not out:
        raise SystemExit("no data/gym_buildings/%s.json" % only)
    return out


def gym_lot(settlement):
    """(rect, level) of the settlement's gym lot, from the town plan in data/placements.json. Never re-authored:
    the pad the building stands on is the one the prep cuts."""
    doc = load(PLACEMENTS)
    plan = (doc.get("settlements") or {}).get(settlement)
    if not plan:
        raise SystemExit("data/placements.json has no settlement %r" % settlement)
    for a in plan["plan"].get("anchors") or []:
        if a.get("role") == "gym":
            return list(a["rect"]), a.get("level")
    raise SystemExit("data/placements.json %s: the town plan has no anchor with role 'gym'" % settlement)


# ------------------------------------------------------------------------------------------------------ geometry
def norm(box):
    x0, y0, z0, x1, y1, z1 = box
    return (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1))


def inside(box, bounds):
    b = norm(box)
    B = norm(bounds)
    return all(B[i] <= b[i] and b[i + 3] <= B[i + 3] for i in range(3))


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def props(state):
    if "[" not in state:
        return {}
    body = state.split("[", 1)[1].split("]", 1)[0]
    out = {}
    for part in body.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------------------------------------------- the model
NOT_SOLID = {
    "minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:water", "minecraft:lava",
    "minecraft:ladder", "minecraft:chain", "minecraft:lantern", "minecraft:soul_lantern", "minecraft:torch",
    "minecraft:wall_torch", "minecraft:scaffolding", "minecraft:rail", "minecraft:light",
}

# What vanilla pops if its carrier is missing. The direction is the cell that must hold it.
#   below: a solid block under it      above: a solid block over it
#   behind: the cell opposite `facing` (a ladder facing east hangs on the block to its west - the state this
#           repository already uses, tools/gym_interiors.py: "ladder[facing=east] ... carried by the west wall")
BEHIND = {"north": (0, 0, 1), "south": (0, 0, -1), "east": (-1, 0, 0), "west": (1, 0, 0)}
NEEDS_BELOW = {
    "minecraft:torch", "minecraft:soul_torch", "minecraft:redstone_torch", "minecraft:rail",
    "minecraft:powered_rail", "minecraft:detector_rail", "minecraft:activator_rail", "minecraft:flower_pot",
    "minecraft:sand", "minecraft:red_sand", "minecraft:gravel", "minecraft:anvil", "minecraft:chipped_anvil",
    "minecraft:damaged_anvil", "minecraft:pointed_dripstone", "minecraft:scaffolding",
}
NEEDS_BEHIND = {"minecraft:ladder", "minecraft:wall_torch", "minecraft:soul_wall_torch"}
LANTERN_STANDS_ON = {"minecraft:chain", "minecraft:cobblestone_wall", "minecraft:stone_brick_wall",
                     "minecraft:mossy_cobblestone_wall", "minecraft:andesite_wall", "minecraft:tuff_wall"}


class Emit:
    """The command list and the voxel model of what it leaves standing, built together so the support check
    reads the same thing the server will."""

    def __init__(self, doc, ground):
        self.doc = doc
        self.bounds = norm(doc["bounds"])
        self.ground = ground              # (x, z) -> the Y of the topmost solid block before this function runs
        self.ops = []
        self.cells = {}                   # (x, y, z) -> block state written, in order
        self.written = 0

    # ---- command writers
    def comment(self, text):
        self.ops.append("# %s" % text)

    def _check(self, box):
        if not inside(box, self.bounds):
            raise SystemExit("%s: a write at %s falls outside the record's bounds %s"
                             % (self.doc["id"], list(norm(box)), list(self.bounds)))

    def fill(self, box, state, mode=None, filt=None):
        self._check(box)
        x0, y0, z0, x1, y1, z1 = norm(box)
        tail = ""
        if mode:
            tail = " " + mode + ((" " + filt) if filt else "")
        self.ops.append("fill %d %d %d %d %d %d %s%s" % (x0, y0, z0, x1, y1, z1, state, tail))
        shell = mode in ("outline", "hollow")
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    if shell and not (x in (x0, x1) or y in (y0, y1) or z in (z0, z1)):
                        if mode == "hollow":
                            self.cells[(x, y, z)] = "minecraft:air"
                        continue
                    if mode == "keep" and self.at(x, y, z) != "minecraft:air":
                        continue
                    self.cells[(x, y, z)] = state
                    self.written += 1

    def set(self, pos, state):
        self._check(tuple(pos) + tuple(pos))
        self.ops.append("setblock %d %d %d %s" % (pos[0], pos[1], pos[2], state))
        self.cells[(pos[0], pos[1], pos[2])] = state
        self.written += 1

    # ---- the model
    def at(self, x, y, z):
        """The block state at a cell after everything written so far; the pad or the rock if nothing wrote it."""
        c = self.cells.get((x, y, z))
        if c is not None:
            return c
        return "minecraft:stone" if y <= self.ground(x, z) else "minecraft:air"

    def solid(self, x, y, z):
        return block_name(self.at(x, y, z)) not in NOT_SOLID


def support_problems(e):
    """Every written cell vanilla would not keep. Read from the finished model, which is the state the server
    is left in, not from the order the commands happen to be in."""
    bad = []
    for (x, y, z), state in sorted(e.cells.items()):
        name = block_name(state)
        p = props(state)
        if name.endswith("_carpet") or name.endswith("_pressure_plate") or name.endswith("_sapling") \
                or name.endswith("_candle") or name in NEEDS_BELOW:
            if not e.solid(x, y - 1, z):
                bad.append(((x, y, z), state, "nothing solid below it"))
        elif name in ("minecraft:lantern", "minecraft:soul_lantern"):
            if p.get("hanging") == "true":
                if not e.solid(x, y + 1, z) and block_name(e.at(x, y + 1, z)) != "minecraft:chain":
                    bad.append(((x, y, z), state, "hanging from air: nothing over it"))
            elif not e.solid(x, y - 1, z) and block_name(e.at(x, y - 1, z)) not in LANTERN_STANDS_ON:
                bad.append(((x, y, z), state, "standing on air: nothing under it"))
        elif name == "minecraft:chain":
            up, dn = block_name(e.at(x, y + 1, z)), block_name(e.at(x, y - 1, z))
            if up == "minecraft:air" and dn == "minecraft:air":
                bad.append(((x, y, z), state, "a chain with nothing over or under it"))
        elif name in NEEDS_BEHIND:
            d = BEHIND.get(p.get("facing", "north"))
            if not e.solid(x + d[0], y, z + d[2]):
                bad.append(((x, y, z), state, "no block behind it (facing=%s)" % p.get("facing")))
    return bad


# --------------------------------------------------------------------------------------------------- the ops
def run_ops(doc, ground):
    """The record's `parts`, in order, as commands and as a voxel model."""
    e = Emit(doc, ground)
    allowed = set(doc["blocks"])
    for i, part in enumerate(doc["parts"]):
        op = part.get("op")
        if op not in OPS:
            raise SystemExit("%s parts[%d]: op %r is not one of %s" % (doc["id"], i, op, ", ".join(OPS)))
        why = part.get("why")
        if why:
            e.comment(why)
        if op == "comment":
            continue
        for state in part_blocks(part):
            if block_name(state) == HEALER:
                raise SystemExit("%s parts[%d]: no gym may hold a healing machine (the brief)" % (doc["id"], i))
            if block_name(state) not in allowed:
                raise SystemExit("%s parts[%d]: %s is not in the record's `blocks` list"
                                 % (doc["id"], i, block_name(state)))
        if op == "fill":
            e.fill(part["box"], part["block"], part.get("mode"), part.get("filter"))
        elif op == "setblock":
            e.set(part["pos"], part["block"])
        elif op == "scatter":
            for p in part["positions"]:
                e.set(p, part["block"])
        elif op == "columns":
            base = part["from_y"]
            for x, z, top in part["cells"]:
                e.fill((x, base, z, x, top, z), part["block"])
        elif op == "gable_roof":
            gable_roof(e, part)
    return e


def part_blocks(part):
    return [part[k] for k in ("block", "gable", "edge", "material") if part.get(k)]


def gable_roof(e, part):
    """A roof of full blocks, stepped one course every two columns, with the ridge down the middle of `run`, the
    gable triangles filled at both ends, and an optional overhang.

    Only geometry: no stair states are invented here (an author who wants stairs passes the state they want as
    `material`, and owns its facing). h(c) = eaves_y + d // 2, d = the distance in from the nearer eave, so the
    roof is watertight: no column is more than one course above its neighbour."""
    x0, z0, x1, z1 = part["box"]
    run = part.get("run", "x")
    ov = int(part.get("overhang", 0))
    eaves = int(part["eaves_y"])
    mat, edge = part["material"], part.get("edge") or part["material"]
    gable, gfrom = part.get("gable"), int(part.get("gable_from_y", eaves))
    a0, a1 = (x0, x1) if run == "x" else (z0, z1)
    b0, b1 = (z0, z1) if run == "x" else (x0, x1)

    def h(c):
        return eaves + min(c - a0, a1 - c) // 2

    for c in range(a0 - ov, a1 + ov + 1):
        edge_column = not (a0 <= c <= a1)
        y = eaves if edge_column else h(c)
        block = edge if edge_column else mat
        box = (c, y, b0 - ov, c, y, b1 + ov) if run == "x" else (b0 - ov, y, c, b1 + ov, y, c)
        e.fill(box, block)
    if gable:
        for c in range(a0, a1 + 1):
            top = h(c) - 1
            if top < gfrom:
                continue
            for b in (b0, b1):
                box = (c, gfrom, b, c, top, b) if run == "x" else (b, gfrom, c, b, top, c)
                e.fill(box, gable)


# ------------------------------------------------------------------------------------------------- the contract
def check_record(doc, lot_rect, lot_level, e):
    """The things every gym building must carry, checked against the model this build just made."""
    bad = []
    bx = norm(doc["bounds"])
    if not (lot_rect[0] <= bx[0] and bx[3] <= lot_rect[2] and lot_rect[1] <= bx[2] and bx[5] <= lot_rect[3]):
        bad.append("bounds %s leave the gym lot %s from data/placements.json: a gym building may not stand on "
                   "the street or on a neighbour's lot" % (list(bx), lot_rect))
    site = doc["site"]
    if site.get("lot_rect") != lot_rect or (lot_level is not None and site.get("lot_level") != lot_level):
        bad.append("site.lot_rect/lot_level %s/%s disagree with the town plan in data/placements.json (%s/%s); "
                   "the plan moved and the building must be re-fitted"
                   % (site.get("lot_rect"), site.get("lot_level"), lot_rect, lot_level))

    spawners = [(p, s) for p, s in e.cells.items() if block_name(s) == SPAWNER]
    if len(spawners) != 1:
        bad.append("%d rctmod:trainer_spawner written; a gym building carries exactly one" % len(spawners))
    else:
        (x, y, z), state = spawners[0]
        if list(doc["leader"]["spawner"]) != [x, y, z]:
            bad.append("the spawner is at %s but leader.spawner says %s" % ([x, y, z], doc["leader"]["spawner"]))
        if doc["leader"]["id"] not in state:
            bad.append("the spawner's TrainerIds do not name leader.id %r: %s" % (doc["leader"]["id"], state))
        if block_name(e.at(x, y - 1, z)) != "minecraft:redstone_block":
            bad.append("no redstone block under the spawner at %s: an unpowered spawner spawns nobody "
                       "(EXP-013 E2)" % [x, y, z])
        for dy in (1, 2):
            if block_name(e.at(x, y + dy, z)) != "minecraft:air":
                bad.append("the spawner needs two air cells over it; %s is %s"
                           % ([x, y + dy, z], e.at(x, y + dy, z)))
    if not [p for p, s in e.cells.items() if block_name(s) == "minecraft:chest"]:
        bad.append("no chest: every gym building carries the leader's chest")
    if any(block_name(s) == HEALER for s in e.cells.values()):
        bad.append("a healing machine: no gym has one")
    return bad


# ------------------------------------------------------------------------------------------------------- output
def ground_for(doc):
    """(x, z) -> the Y of the topmost solid block the building stands on, before it is built."""
    site = doc["site"]
    kind = (site.get("ground") or {}).get("kind", "lot_level")
    if kind == "lot_level":
        level = int(site["lot_level"])
        return lambda x, z: level
    if kind == "heightmap":
        G = ground_mod.load()
        return lambda x, z: G(x, z)
    raise SystemExit("%s: site.ground.kind %r is not lot_level or heightmap" % (doc["id"], kind))


def build_one(doc):
    lot_rect, lot_level = gym_lot(doc["settlement"])
    e = run_ops(doc, ground_for(doc))
    bad = support_problems(e)
    if bad:
        raise SystemExit("%s: %d block(s) vanilla would not keep standing (first 5):\n  %s"
                         % (doc["id"], len(bad), "\n  ".join("%s %s: %s" % b for b in bad[:5])))
    problems = check_record(doc, lot_rect, lot_level, e)
    if problems:
        raise SystemExit("%s:\n  %s" % (doc["id"], "\n  ".join(problems)))
    return e, lot_rect, lot_level


def summary(doc, e, lot_rect):
    bx = norm(doc["bounds"])
    f = doc["site"]["footprint"]
    return {
        "id": doc["id"], "leader": doc["leader"], "settlement": doc["settlement"],
        "supersedes_donor": doc.get("supersedes_donor"),
        "lot_rect": lot_rect, "lot_level": doc["site"].get("lot_level"),
        "footprint": f, "footprint_size": [f[2] - f[0] + 1, f[3] - f[1] + 1],
        "floor_y": doc["site"]["floor_y"], "stand_y": doc["site"]["stand_y"],
        "bounds": list(bx), "height_above_floor": bx[4] - doc["site"]["floor_y"],
        "commands": len([l for l in e.ops if not l.startswith("#")]),
        "cells_written": e.written,
        "rooms": doc.get("rooms", []), "route": doc.get("route", []),
        "no_build": doc.get("no_build", []), "trainers": doc.get("trainers", []),
    }


def write_function(name, lines):
    cmds = function_limits.ensure_loaded(lines)
    refused = function_limits.check_lines(cmds, name)
    if refused:
        raise SystemExit("%s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:3]))
    (FUNCS / ("%s.mcfunction" % name)).write_text("\n".join(cmds) + "\n", encoding="utf-8")
    return cmds


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("report", "build"):
        q = sub.add_parser(name)
        q.add_argument("--gym", default=None, help="one record only (default: every data/gym_buildings/*.json)")
        q.add_argument("--source-root", default=None)
        if name == "build":
            q.add_argument("--out", default=str(PACK))
    a = p.parse_args(argv)

    if a.source_root:
        os.environ["COBBLERS_SOURCE_ROOT"] = a.source_root
    recs = records(a.gym)
    if not recs:
        raise SystemExit("data/gym_buildings holds no record; there is nothing to generate (fail closed)")

    out, done = [], []
    for _path, doc in recs:
        e, lot_rect, _lvl = build_one(doc)
        out.append((doc, e, summary(doc, e, lot_rect)))

    if a.cmd == "build":
        if PACK.exists():
            shutil.rmtree(PACK)
        FUNCS.mkdir(parents=True)
        (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                          "Cobblers: the authored gym buildings (tools/gym_buildings.py)"}},
                                          indent=2) + "\n", encoding="utf-8")
        for doc, e, _s in out:
            write_function(doc["id"], e.ops)
            done.append(doc["id"])
        (FUNCS / "index.txt").write_text("\n".join(done) + "\n", encoding="utf-8")

    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "report.json").write_text(json.dumps({"gyms": [s for _d, _e, s in out]}, indent=1) + "\n",
                                        encoding="utf-8")
    seats = [dict(t, gym=s["id"]) for _d, _e, s in out for t in s["trainers"]]
    (REPORT / "trainer_seats.json").write_text(json.dumps(
        {"note": "handoff for trainer-balance-designer: seats only, no rosters. A seat is placed only once "
                 "data/trainers.json and data/route_trainers.json carry its id.", "trainers": seats},
        indent=1) + "\n", encoding="utf-8")
    (REPORT / "no_build.json").write_text(json.dumps(
        {"note": "handoff: the boxes that want the scene runtime's adventure-mode box (tools/scenes_pack.py "
                 "no_build), which needs a scene record in data/scenes.json. Not wired here.",
         "boxes": [dict(b, gym=s["id"]) for _d, _e, s in out for b in s["no_build"]]}, indent=1) + "\n",
        encoding="utf-8")

    for doc, _e, s in out:
        w, d = s["footprint_size"]
        print("%s (%s): %dx%d, floor y%d, %d above the floor, %d commands, %d cells, %d room(s), %d route step(s)"
              % (s["id"], s["leader"]["name"], w, d, s["floor_y"], s["height_above_floor"],
                 s["commands"], s["cells_written"], len(s["rooms"]), len(s["route"])))
        if a.cmd == "report":
            for r in s["route"]:
                print("   %-2s %-20s %-6s %s" % (r.get("step"), r.get("id"), r.get("how"), r.get("why")))
    if a.cmd == "build":
        print("wrote", PACK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
