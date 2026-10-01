#!/usr/bin/env python
"""Gym interiors: the healers out of all eight gyms, and gym 1's works carved under its lot, as datapack functions.

From data/gym_interiors.json (the authored model) and data/placements.json (every shell's position, size and
rotation, which is never re-authored). Writes the pack `cobblers_gym_interiors`:

  cobblers:gym_interiors/healers        one `fill <shell box> <replacement> replace cobblemon:healing_machine`
                                        per gym, split so no fill passes the 32,768-block limit. The owner's call,
                                        2026-09-29: no healing machine in any gym. Overriding the Cobbleverse
                                        template NBT is refused on licence, and the templates are placed by
                                        resource id, so the removal is a post-placement overwrite - the same thing
                                        tools/town_dressing.py does to the towns. Driven by the shell box alone, so
                                        a one-block error in the measured healer cell cannot leave one standing.
  cobblers:gym_interiors/gym1           Brock's works: a scaffolding shaft down from the cell the healing machine
                                        stood in, the cutting floor, the pit with the unfinished wall in it, the
                                        climb, the high ledge and the foreman's tally, and a one-way chute back.

Where the rooms are:
  ground     the heightmap, rounded (tools/ground.py), never a world, and only to check cover: every carved
             room's ceiling block is at least `rules.min_cover` under the ground over it. Nothing here reads a
             world to decide a position (tools/ground_rule.py)
  shell      derived from data/placements.json through the same transform tools/place_donor.py box() and
             tools/place_town.py rotate() use. The only measured numbers are the template-relative healing
             machine and trainer spawner cells recorded in data/gym_interiors.json `measured`; they are
             expectations the audit checks, and they drive nothing
  order      after the pack donors (tools/reapply.py R9), which are placed whole and would erase anything written
             into them first: tools/reapply.py R16E, after the shrines

tools/gym_interiors_audit.py checks the written functions independently: it re-derives every shell box from
data/placements.json, replays every command into a voxel model of the dig and checks the contracts (cover, rock
between rooms, standable seats, the sight rule, falls, the suppression box, the block list) against
data/gym_interiors.json and data/spawn_blocks.json, never against this tool's report.

  python tools/gym_interiors.py build [--out build/datapacks/cobblers_gym_interiors] [--source-root <root>]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import place_donor  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_gym_interiors"
FUNCS = PACK / "data" / "cobblers" / "function" / "gym_interiors"
REPORT = ROOT / "derived" / "gym_interiors"
DATA = ROOT / "data" / "gym_interiors.json"
PLACEMENTS = ROOT / "data" / "placements.json"
HEALER = "cobblemon:healing_machine"
FILL_LIMIT = 32768

# The ground rule (tools/ground_rule.py): nothing here reads a world at all.
WORLD_READS = set()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ derived geometry
def donor_records(placements):
    return {p["id"]: p for p in placements["placements"] if isinstance(p, dict) and p.get("id")}


def shell_box(rec):
    """((x0,y0,z0), (x1,y1,z1)) the placed template occupies, from its own record. Never authored."""
    return place_donor.box(rec)


def to_world(rec, cell):
    """A template-relative cell mapped through the placement's own rotation and anchor."""
    import place_town
    dx, dz = place_town.rotate(cell[0], cell[2], rec.get("rotation", "none"))
    p = rec["position"]
    return (p["x"] + dx, p["y"] + cell[1], p["z"] + dz)


# ------------------------------------------------------------------------------------------------------- commands
class Build:
    """An ordered list of block writes. Fills and setblocks only, so the audit can replay the text exactly."""

    def __init__(self):
        self.ops = []

    def fill(self, box, state, why=None):
        x0, y0, z0, x1, y1, z1 = box
        if why:
            self.ops.append("# %s" % why)
        self.ops.append("fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, state))

    def set(self, pos, state, why=None):
        if why:
            self.ops.append("# %s" % why)
        self.ops.append("setblock %d %d %d %s" % (pos[0], pos[1], pos[2], state))

    def comment(self, text):
        self.ops.append("# %s" % text)


def split_box(box, limit=FILL_LIMIT):
    """The box as y-slabs, each under the /fill volume limit."""
    x0, y0, z0, x1, y1, z1 = box
    area = (abs(x1 - x0) + 1) * (abs(z1 - z0) + 1)
    step = max(1, limit // max(1, area))
    lo, hi = min(y0, y1), max(y0, y1)
    out = []
    y = lo
    while y <= hi:
        out.append((x0, y, z0, x1, min(hi, y + step - 1), z1))
        y += step
    return out


def healer_commands(doc, recs):
    """One fill per gym (split for Misty's 46,080-block shell), and the removal's own report rows."""
    b, rows = Build(), []
    b.comment("no healing machine in any gym (the owner, 2026-09-29; data/gym_interiors.json healers).")
    b.comment("Driven by the shell box from data/placements.json, so it cannot miss a machine that stands one block off.")
    for g in doc["healers"]["gyms"]:
        rec = recs.get(g["donor"])
        if rec is None:
            raise SystemExit("data/gym_interiors.json healers names %s, which data/placements.json does not have" % g["donor"])
        (x0, y0, z0), (x1, y1, z1) = shell_box(rec)
        parts = split_box((x0, y0, z0, x1, y1, z1))
        b.comment("%s (%s): %s" % (g["gym"], g["leader"], g["why"]))
        for p in parts:
            b.ops.append("fill %d %d %d %d %d %d %s replace %s" % (p[0], p[1], p[2], p[3], p[4], p[5],
                                                                   g["replacement"], HEALER))
        rows.append({"gym": g["gym"], "donor": g["donor"], "shell_box": [x0, y0, z0, x1, y1, z1],
                     "replacement": g["replacement"], "fills": len(parts),
                     "expect_healer_world": list(to_world(rec, g["expect_at"])),
                     "check": "execute if block %d %d %d %s" % (*to_world(rec, g["expect_at"]), HEALER)})
    return b, rows


# --------------------------------------------------------------------------------------------- gym 1: Brock's works
def gym1_commands(gym, recs):
    """Brock's works. Every coordinate here is either a room box from data/gym_interiors.json or a fitting inside one;
    the audit checks that, so nothing may stray outside the dig."""
    rooms = {r["id"]: r["box"] for r in gym["rooms"]}
    b = Build()

    b.comment("gym 1, Brock: the works under the unfinished wall (data/gym_interiors.json gyms[gym1]).")
    b.comment("Carved below the gym lot, ADR-004. The standing shell is untouched but for the one shaft column.")

    # ---- carve --------------------------------------------------------------------------------------------------
    b.comment("-- the carve")
    for rid in ("r1_cutting", "c1_door", "r2_wall", "c2_door", "r3_tally", "c3_return"):
        x0, y0, z0, x1, y1, z1 = rooms[rid]
        for part in split_box((x0, y0, z0, x1, y1, z1)):
            b.ops.append("fill %d %d %d %d %d %d minecraft:air" % part)
    b.fill((1817, 136, 3685, 1817, 140, 3685), "minecraft:air", "the shaft, through the rock between the cutting floor and the shell's base course")
    b.fill(tuple(gym["shell_penetration"][:3]) + tuple(gym["shell_penetration"][3:]), "minecraft:air",
           "the only cells of the standing building this writes: the healer's cell, the floor course and the base course under it")

    # ---- floors -------------------------------------------------------------------------------------------------
    b.comment("-- floors")
    b.fill((1814, 130, 3679, 1824, 130, 3689), "minecraft:stone_bricks", "the cutting floor's paving")
    b.fill((1822, 130, 3690, 1823, 130, 3691), "minecraft:stone_bricks", "the doorway's sill")
    b.fill((1814, 118, 3692, 1836, 118, 3701), "minecraft:cobblestone", "the pit floor")
    b.fill((1814, 118, 3694, 1836, 118, 3701), "minecraft:hay_block",
           "the packing straw under the wall: contract G3, a fall from the climb takes 80% less")
    b.fill((1816, 118, 3692, 1836, 118, 3693), "minecraft:hay_block",
           "and under the high ledge, whose 16-block drop the audit found landing on bare stone. The two columns "
           "beside the masons' ladder stay cobble: that is where you climb down on purpose")
    b.fill((1815, 130, 3692, 1823, 130, 3693), "minecraft:stone_bricks", "the low ledge, the way in")
    b.fill((1829, 134, 3692, 1836, 134, 3694), "minecraft:stone_bricks", "the high ledge, the way on: two above the low ledge and five clear of it")
    b.fill((1835, 134, 3689, 1836, 134, 3691), "minecraft:stone_bricks", "the tally door's sill")
    b.fill((1828, 134, 3680, 1836, 134, 3688), "minecraft:stone_bricks", "the foreman's floor")
    b.fill((1825, 134, 3681, 1827, 134, 3682), "minecraft:stone_bricks", "the chute's floor")
    b.fill((1823, 130, 3681, 1824, 130, 3682), "minecraft:hay_block", "the straw the chute drops you onto, four below it")

    # ---- the shaft ----------------------------------------------------------------------------------------------
    b.comment("-- the works shaft, where the healing machine stood")
    b.fill((1817, 131, 3685, 1817, 142, 3685), "minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]",
           "scaffolding, not a ladder: a column standing on the paving needs no wall behind it, so nothing here "
           "depends on a block of the shell whose state was never measured. Climbable both ways; its top cell is "
           "the gym floor's own standing level, so a player steps straight off it into the hall")

    # ---- the pit: the way down ----------------------------------------------------------------------------------
    b.comment("-- the masons' ladder down the pit's west wall")
    b.fill((1814, 119, 3692, 1814, 131, 3692), "minecraft:ladder[facing=east]",
           "carried by the pit's uncut west wall at x1813")

    # ---- the climb ----------------------------------------------------------------------------------------------
    b.comment("-- the unfinished wall: the only continuous climb, found by looking")
    b.fill((1829, 119, 3698, 1836, 123, 3701), "minecraft:stone_bricks", "the built part of the wall; its crest stands at 124")
    b.fill((1836, 119, 3697, 1836, 119, 3697), "minecraft:cobblestone", "the rubble ramp, step 1")
    b.fill((1835, 119, 3697, 1835, 120, 3697), "minecraft:cobblestone", "step 2")
    b.fill((1834, 119, 3697, 1834, 121, 3697), "minecraft:cobblestone", "step 3")
    b.fill((1833, 119, 3697, 1833, 122, 3697), "minecraft:cobblestone", "step 4, onto the crest")
    b.fill((1836, 124, 3697, 1836, 130, 3697), "minecraft:ladder[facing=west]",
           "the east-wall ladders off the crest, carried by the pit's uncut east wall at x1837")
    b.fill((1828, 129, 3695, 1835, 129, 3697), "minecraft:oak_planks", "the scaffold deck")
    b.fill((1820, 129, 3696, 1827, 129, 3696), "minecraft:oak_planks",
           "the dead end: a walkway that simply stops, and from the pit floor you can see it stops")
    b.fill((1830, 129, 3698, 1830, 129, 3700), "minecraft:oak_planks", "the walkway to the last ladders")
    b.fill((1830, 130, 3701, 1830, 135, 3701), "minecraft:ladder[facing=north]",
           "the last ladders, carried by the pit's uncut south wall at z3702")
    b.fill((1828, 134, 3698, 1833, 134, 3700), "minecraft:stone_bricks", "the top of the wall")
    b.fill((1830, 134, 3695, 1830, 134, 3697), "minecraft:oak_planks",
           "the jib beam: one plank wide, across the pit to the high ledge. Miss it and you land on the deck five below")

    # ---- fittings -----------------------------------------------------------------------------------------------
    b.comment("-- the cutting floor's work")
    b.set((1816, 131, 3681), "minecraft:stonecutter[facing=south]")
    b.set((1820, 131, 3680), "minecraft:stonecutter[facing=south]")
    b.fill((1815, 131, 3687, 1816, 132, 3688), "minecraft:stone_bricks", "squared stone, stacked")
    b.fill((1819, 131, 3683, 1820, 131, 3684), "minecraft:chiseled_stone_bricks", "the chiselled course, set aside")
    for p in ((1816, 135, 3681), (1821, 135, 3686), (1818, 135, 3688)):
        b.set(p, "minecraft:lantern[hanging=true]")

    b.comment("-- light in the pit")
    for p in ((1816, 131, 3693), (1822, 131, 3693), (1833, 135, 3692), (1836, 135, 3692),
              (1828, 130, 3695), (1834, 130, 3695), (1820, 119, 3693), (1830, 119, 3693), (1824, 119, 3692)):
        b.set(p, "minecraft:lantern[hanging=false]")

    b.comment("-- the foreman's tally")
    b.set((1832, 135, 3683), "minecraft:chest[facing=south]")
    b.fill((1834, 135, 3682, 1835, 136, 3683), "minecraft:stone_bricks", "the works store")
    for p in ((1831, 137, 3684), (1834, 137, 3686)):
        b.set(p, "minecraft:lantern[hanging=true]")
    return b


# ----------------------------------------------------------------------------------------------------------- build
def build(a):
    doc = load(DATA)
    recs = donor_records(load(PLACEMENTS))
    allowed = set(doc["blocks"]["ids"])

    if PACK.exists():
        shutil.rmtree(PACK)
    FUNCS.mkdir(parents=True)
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                      "Cobblers: gym interiors (tools/gym_interiors.py)"}}, indent=2) + "\n", encoding="utf-8")
    REPORT.mkdir(parents=True, exist_ok=True)

    names, report = [], {"healers": [], "gyms": []}

    healers, rows = healer_commands(doc, recs)
    write_function("healers", healers.ops, allowed)
    names.append("healers")
    report["healers"] = rows
    print("healers: %d gyms, %d fills" % (len(rows), sum(r["fills"] for r in rows)))

    built = [g for g in doc["gyms"] if g.get("built")]
    if not built:
        raise SystemExit("data/gym_interiors.json: no gym is `built`; there is nothing to generate (fail closed)")
    for gym in built:
        if gym["id"] != "gym1":
            raise SystemExit("%s is marked built but this tool only knows gym 1's shape "
                             "(docs/mechanics/GYM_INTERIORS.md: gym 1 only, before the other seven)" % gym["id"])
        rec = recs[gym["donor"]]
        (sx0, sy0, sz0), (sx1, sy1, sz1) = shell_box(rec)
        if [sx0, sy0, sz0, sx1, sy1, sz1] != gym["shell"]["expect_box"]:
            raise SystemExit("%s: the shell box derived from data/placements.json is %s but the record expects %s; "
                             "the placement moved and the interior must be re-fitted"
                             % (gym["id"], [sx0, sy0, sz0, sx1, sy1, sz1], gym["shell"]["expect_box"]))
        b = gym1_commands(gym, recs)
        write_function(gym["id"], b.ops, set(gym["blocks"]))
        names.append(gym["id"])
        report["gyms"].append({
            "id": gym["id"], "donor": gym["donor"], "shell_box": [sx0, sy0, sz0, sx1, sy1, sz1],
            "dig": gym["dig"], "rooms": {r["id"]: r["box"] for r in gym["rooms"]},
            "commands": len([l for l in b.ops if not l.startswith("#")]),
            "entrance": gym["entrance"],
            "leader_spawner": list(to_world(rec, doc["measured"]["small_gym_relative"]["trainer_spawner"])),
            "trainers": [{"id": t["id"], "seat": t["seat"], "yaw": t["yaw"], "sight_distance": t["sight_distance"],
                          "room": t["room"]} for t in gym["trainers"]]})
        print("%s: %d commands, %d rooms" % (gym["id"], report["gyms"][-1]["commands"], len(gym["rooms"])))

    (FUNCS / "index.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    (REPORT / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    # the handoff: the trainer seats in the shape data/route_trainers.json trainers[] takes. Rosters, skins and
    # dialogue are trainer-balance-designer's; nothing is placed until data/trainers.json carries these ids.
    seats = [{"id": t["id"], "name": t["working_name"], "seat": t["seat"], "yaw": t["yaw"],
              "eye_contact": True, "sight_distance": t["sight_distance"],
              "why": t["why_unavoidable"], "gym": g["id"], "room": t["room"]}
             for g in built for t in g["trainers"]]
    (REPORT / "trainer_seats.json").write_text(json.dumps(
        {"note": "handoff for trainer-balance-designer: seats only, no rosters. Copy into data/route_trainers.json "
                 "trainers[] with a skin, and add the matching records to data/trainers.json and the quest fields "
                 "quest.<id>.defeated to data/progression.json.", "trainers": seats}, indent=1) + "\n", encoding="utf-8")
    (REPORT / "no_build.json").write_text(json.dumps(
        {"note": "handoff: contract G4. These boxes want the scene runtime's adventure-mode box "
                 "(tools/scenes_pack.py no_build), which needs a scene record in data/scenes.json. Not wired here.",
         "boxes": [{"gym": g["id"], **nb} for g in built for nb in g["no_build"]]}, indent=1) + "\n", encoding="utf-8")
    print("wrote", PACK)
    return 0


def write_function(name, lines, allowed):
    bad = sorted({block_name(state_of(l)) for l in lines if not l.startswith("#")} - allowed)
    if bad:
        raise SystemExit("%s: blocks not in the record's `blocks` list: %s" % (name, bad))
    cmds = function_limits.ensure_loaded(lines)
    refused = function_limits.check_lines(cmds, name)
    if refused:
        raise SystemExit("%s: %d command(s) the server would refuse: %s" % (name, len(refused), refused[:3]))
    (FUNCS / ("%s.mcfunction" % name)).write_text("\n".join(cmds) + "\n", encoding="utf-8")


def state_of(line):
    """The block state a fill or setblock writes (the `replace <filter>` tail is a filter, not a write)."""
    parts = line.split()
    if parts[0] == "setblock":
        return parts[4]
    if parts[0] == "fill":
        return parts[7]
    raise SystemExit("gym_interiors writes only fill and setblock; got %r" % line)


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("build")
    q.add_argument("--out", default=str(PACK))
    q.add_argument("--source-root", default=None)
    a = p.parse_args(argv)
    return build(a)


if __name__ == "__main__":
    raise SystemExit(main())
