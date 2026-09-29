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


# ----------------------------------------------------------------------------------- gyms 2-7: the carve helpers
def carve(b, gym, ids):
    """Air out the named rooms. Every box comes from data/gym_interiors.json, never from a number written here."""
    rooms = {r["id"]: r["box"] for r in gym["rooms"]}
    b.comment("-- the carve")
    for rid in ids:
        for part in split_box(tuple(rooms[rid])):
            b.ops.append("fill %d %d %d %d %d %d minecraft:air" % part)


def rooms_of(gym):
    return {r["id"]: tuple(r["box"]) for r in gym["rooms"]}


# --------------------------------------------------------------------------------- gym 2: Misty's cistern
def gym2_commands(gym, recs):
    """The cistern under the lake: a well 38 blocks down the template's own rock plinth, a drawing floor with a
    basin in it, a one-way fall into a surface-swum race, three mouths at its head and the ledger gallery above."""
    b = Build()
    P, D = "minecraft:prismarine_bricks", "minecraft:dark_prismarine"
    b.comment("gym 2, Misty: the cistern under the lake (data/gym_interiors.json gyms[gym2]).")
    b.comment("Misty's hall stands 26 blocks up on the template's rock, so her well is the deepest of the six.")

    carve(b, gym, ["r1_cistern", "c1_fall", "r2_race", "r3_gallery", "c2_return"])
    b.fill((1620, 100, 2867, 1620, 106, 2867), "minecraft:air", "the well through the rock between the cistern's ceiling and the shell's foot")
    b.fill((1620, 107, 2867, 1620, 133, 2867), "minecraft:air",
           "the well through the shell itself: 25 courses of the template's rock plinth, its floor course and the "
           "healer's cell. The declared shell penetration, and the only part of the standing building written")

    b.comment("-- floors")
    b.fill((1610, 94, 2862, 1626, 94, 2876), P, "the drawing floor")
    b.fill((1598, 98, 2872, 1607, 98, 2876), P, "the ledger gallery's floor")
    b.fill((1604, 85, 2872, 1620, 85, 2876), P, "the race's bed")
    b.fill((1617, 91, 2864, 1623, 91, 2870), P, "the basin's floor, three below the drawing floor")

    b.comment("-- the water")
    b.fill((1617, 92, 2864, 1623, 94, 2870), "minecraft:water", "the basin the well's foot stands in")
    b.fill((1604, 86, 2872, 1620, 87, 2876), "minecraft:water",
           "the race: two deep with two of air over it, so it is swum at the surface and nothing here asks a player "
           "to hold their breath (contract G2)")
    b.fill((1613, 94, 2874, 1614, 94, 2875), "minecraft:air", "the overflow's mouth, cut back through the drawing floor")
    b.fill((1613, 90, 2874, 1614, 91, 2875), "minecraft:air", "and its shaft, between the door box and the race's own air")
    b.fill((1608, 86, 2872, 1610, 87, 2875), D, "the island the rescue swimmer stands on: four of the race's five lanes")

    b.comment("-- the three mouths at the race's head; two stop after five, one goes up")
    for z, top in ((2872, 91), (2876, 91), (2874, 94)):
        b.fill((1602, 86, z, 1602, top, z), "minecraft:water")
        b.fill((1603, 86, z, 1603, 87, z), "minecraft:water", "the slot from the race into it")
    b.fill((1602, 95, 2874, 1602, 98, 2874), "minecraft:water", "the true mouth's last four, up to the gallery's floor")
    b.fill((1602, 98, 2874, 1602, 98, 2874), "minecraft:water", "and the hole it makes in that floor")
    for p in ((1603, 88, 2874), (1601, 90, 2874), (1603, 92, 2874)):
        b.set(p, "minecraft:sea_lantern")
    b.comment("the light is the whole clue: the true mouth is lit from inside the rock, the other two are dark")

    b.comment("-- the well")
    b.fill((1620, 92, 2867, 1620, 94, 2867), "minecraft:scaffolding[bottom=false,distance=0,waterlogged=true]",
           "its foot, standing in the basin")
    b.fill((1620, 95, 2867, 1620, 133, 2867), "minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]",
           "and the rest of it, up to the gym floor's own standing level")

    b.comment("-- the cistern's fitout")
    b.fill((1611, 95, 2863, 1612, 96, 2864), D, "cut stone stacked by the stair")
    for p in ((1624, 95, 2863), (1624, 95, 2875)):
        b.set(p, "minecraft:barrel[facing=up]")
    for p in ((1612, 98, 2866), (1624, 98, 2870), (1616, 98, 2874), (1622, 98, 2863)):
        b.set(p, "minecraft:lantern[hanging=true]")

    b.comment("-- the race and the island")
    for p in ((1606, 89, 2873), (1612, 89, 2875), (1618, 89, 2873)):
        b.set(p, "minecraft:sea_lantern")
    b.fill((1609, 88, 2873, 1609, 88, 2873), "minecraft:dark_oak_fence", "the swimmer's oar rack")

    b.comment("-- the ledger gallery: the record of every arrival")
    b.set((1600, 99, 2874), "minecraft:lectern[facing=east]")
    b.set((1599, 99, 2873), "minecraft:chest[facing=east]")
    for p in ((1601, 99, 2876), (1603, 99, 2876), (1605, 99, 2876)):
        b.set(p, "minecraft:barrel[facing=up]")
    b.fill((1598, 99, 2872, 1598, 100, 2872), "minecraft:dark_oak_planks", "the ledger board's frame")
    for p in ((1600, 102, 2873), (1605, 102, 2875)):
        b.set(p, "minecraft:lantern[hanging=true]")
    return b


# ------------------------------------------------------------------------------------ gym 3: Surge's cable adit
def gym3_commands(gym, recs):
    """The adit into Vessu: one hall fifteen blocks tall because the ridge over it allows one, four cable trenches
    cut nine deep in its floor, and a catwalk you read them from behind a grate you cannot step through."""
    b = Build()
    DS, DB = "minecraft:polished_deepslate", "minecraft:deepslate_bricks"
    CU = "minecraft:waxed_cut_copper"
    b.comment("gym 3, Lt Surge: the adit into Vessu (data/gym_interiors.json gyms[gym3]).")
    b.comment("The heightmap runs y174 at the shell's west face and y197 at its east: this is the one gym cut into a hill.")

    carve(b, gym, ["r1_run", "c2_door", "r3_relay", "c3_return"])
    b.fill((1743, 168, 1418, 1743, 172, 1418), "minecraft:air", "the riser through the rock between the catwalk and the shell")
    b.fill((1743, 173, 1418, 1743, 175, 1418), "minecraft:air", "the declared shell penetration: base course, floor course, healer's cell")

    b.comment("-- floors")
    b.fill((1735, 156, 1402, 1748, 156, 1418), DS, "the run's floor")
    b.fill((1736, 156, 1421, 1748, 156, 1427), DS, "the relay chamber's floor")

    b.comment("-- the run: solid, then four lines cut out of it")
    b.fill((1736, 157, 1406, 1748, 165, 1418), DB,
           "the mass the trenches are cut from. North of z1406 it is left open: that is the crosscut where the four "
           "lines begin, and x1735 is left open as the aisle the ladder comes down")
    for x in (1738, 1744, 1747):
        b.fill((x, 157, 1406, x, 165, 1416), "minecraft:air", "a line, cut nine deep")
        b.fill((x, 156, 1406, x, 156, 1416), CU, "its cable")
    b.fill((1741, 157, 1406, 1741, 165, 1418), "minecraft:air", "the second line, which runs all the way through")
    b.fill((1741, 156, 1406, 1741, 156, 1418), CU, "its cable")
    b.comment("-- and the fall of rock that plugs three of them, visible from the catwalk and from nowhere else")
    b.fill((1738, 157, 1411, 1738, 165, 1411), DB, "the first line, plugged at z1411")
    b.fill((1744, 157, 1409, 1744, 165, 1409), DB, "the third, at z1409")
    b.fill((1747, 157, 1413, 1747, 165, 1413), DB, "the fourth, at z1413")

    b.comment("-- the catwalk, and the grate that stops you stepping off it")
    b.fill((1736, 166, 1414, 1748, 166, 1418), CU, "the deck")
    b.fill((1736, 167, 1414, 1748, 168, 1414), "minecraft:copper_grate",
           "two high, so it cannot be jumped, and see-through, so the whole run is read over it. Without it a player "
           "could drop off the deck onto the trench walls and walk round the lineman")
    b.fill((1743, 167, 1418, 1743, 175, 1418), "minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]",
           "the cable riser. Scaffolding in every gym for the same reason: its top three cells stand inside the shell, "
           "whose blocks were never measured, and a column standing on its own foot needs no wall behind it")
    b.fill((1735, 157, 1417, 1735, 167, 1417), "minecraft:ladder[facing=east]",
           "the aisle ladder, carried by the run's own uncut west wall at x1734")

    b.comment("-- the relay chamber: the board, the drums, the store and the stair out")
    b.fill((1736, 157, 1427, 1748, 160, 1427), CU, "the breaker board across the chamber's south wall")
    b.fill((1738, 161, 1427, 1746, 162, 1427), "minecraft:copper_grate", "its cabinet fronts")
    b.fill((1737, 157, 1421, 1737, 159, 1421), "minecraft:waxed_copper_block", "a cable drum")
    b.fill((1739, 157, 1426, 1740, 158, 1426), "minecraft:waxed_copper_block", "two more")
    b.set((1744, 157, 1426), "minecraft:chest[facing=north]")
    for p in ((1738, 157, 1424), (1746, 157, 1423)):
        b.set(p, "minecraft:barrel[facing=up]")
    b.fill((1747, 157, 1427, 1747, 169, 1427), DB, "the stair ladder's pier")
    b.fill((1747, 157, 1426, 1747, 169, 1426), "minecraft:ladder[facing=north]", "twelve up to the top sill")
    b.fill((1746, 168, 1419, 1748, 168, 1425), DB, "the sill floor along the chamber's top, stopping one short of the ladder so it does not cap it")
    for p in ((1738, 163, 1426), (1744, 163, 1426), (1741, 163, 1422)):
        b.set(p, "minecraft:lantern[hanging=true]")
    for p in ((1737, 158, 1409), (1737, 158, 1415), (1745, 158, 1404), (1739, 168, 1416), (1746, 168, 1416)):
        b.set(p, "minecraft:lantern[hanging=false]")
    return b


# ------------------------------------------------------------------------------- gym 4: Erika's beds and drains
def gym4_commands(gym, recs):
    """The beds below the glasshouse: a cellar four blocks tall under a dead-flat lot, planters on legs with a
    hand's width of water under them, and one drain that is open."""
    b = Build()
    M, MC = "minecraft:mossy_stone_bricks", "minecraft:mossy_cobblestone"
    b.comment("gym 4, Erika: the beds below the glasshouse (data/gym_interiors.json gyms[gym4]).")
    b.comment("The heightmap is y110 across the whole lot, so nothing here may have a ceiling over y107: the flattest")
    b.comment("site of the six, and the reason the way on is underneath rather than ahead.")

    carve(b, gym, ["r1_beds", "c1_drain", "r2_cistern", "c2_climb", "r3_return"])
    b.fill((4318, 104, 1485, 4318, 108, 1485), "minecraft:air", "the ladder shaft through the rock between the cellar and the shell")
    b.fill((4318, 109, 1485, 4318, 111, 1485), "minecraft:air", "the declared shell penetration")

    b.comment("-- floors")
    b.fill((4306, 98, 1481, 4322, 98, 1493), M, "the cellar's floor")
    b.fill((4306, 95, 1497, 4316, 95, 1504), M, "the cistern's floor")
    b.fill((4312, 102, 1493, 4316, 102, 1503), "minecraft:cherry_planks", "the potting passage's floor")
    b.fill((4316, 102, 1493, 4316, 102, 1493), "minecraft:air", "and the hatch in it, over the cellar's east aisle")

    b.comment("-- the beds: soil at y100 on legs, with the drains running under them at y99")
    for (x0, z0, x1, z1) in ((4307, 1482, 4312, 1485), (4307, 1487, 4312, 1490), (4319, 1487, 4322, 1492)):
        b.fill((x0, 100, z0, x1, 100, z1), "minecraft:rooted_dirt", "a bed")
        b.fill((x0, 101, z0, x1, 101, z1), "minecraft:moss_block", "grown over")
        b.set((x0, 99, z0), MC)
        b.set((x1, 99, z1), MC)
        b.set((x0, 99, z1), MC)
        b.set((x1, 99, z0), MC)
    b.comment("the legs are the corners only: every bed has a hand's width of air or water under it, and the players")
    b.comment("who look will see that one of them has water moving in it")

    b.comment("-- the hedge, and the one gap in it")
    b.fill((4314, 99, 1481, 4314, 102, 1493), "minecraft:azalea_leaves", "the azalea hedge, wall to wall")
    b.fill((4314, 99, 1488, 4314, 101, 1488), "minecraft:air", "its gap, where the gardener stands")

    b.comment("-- the drain that is open: one block high, five long, flooded, and it discharges into the cistern")
    b.fill((4310, 98, 1494, 4310, 98, 1496), M, "its bed")
    b.fill((4310, 100, 1494, 4310, 100, 1497), M, "its cap, one over the water, so a walking player does not fit")
    b.fill((4310, 99, 1494, 4310, 99, 1497), "minecraft:water", "the water itself")
    b.fill((4310, 98, 1497, 4310, 98, 1497), "minecraft:air", "and the hole it falls through into the cistern")
    b.fill((4318, 99, 1485, 4318, 111, 1485), "minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]",
           "the trellis ladder: scaffolding, as in every gym, because its top cells stand inside the shell")
    b.fill((4310, 99, 1491, 4310, 99, 1493), "minecraft:air", "the mouth under the middle bed, kept dry so it can be entered on foot")

    b.comment("-- the cistern: the water store, the partition and the way up")
    b.fill((4306, 96, 1500, 4316, 99, 1500), MC, "the partition")
    b.fill((4312, 96, 1500, 4314, 99, 1500), "minecraft:air", "and its one gap")
    b.fill((4307, 96, 1502, 4311, 96, 1503), "minecraft:water", "the store, one deep and waded through")
    b.fill((4316, 96, 1503, 4316, 103, 1503), M, "the climb's backing wall")
    b.fill((4315, 96, 1503, 4315, 103, 1503), "minecraft:ladder[facing=west]", "the ladder out")
    for p in ((4308, 97, 1498), (4314, 97, 1498), (4308, 97, 1504), (4313, 97, 1502)):
        b.set(p, "minecraft:lantern[hanging=false]")
    b.set((4307, 96, 1499), "minecraft:composter")
    b.set((4309, 96, 1499), "minecraft:barrel[facing=up]")
    b.set((4315, 96, 1499), "minecraft:chest[facing=west]")

    b.comment("-- the potting passage")
    b.fill((4312, 103, 1497, 4312, 104, 1498), "minecraft:oak_planks", "the potting bench")
    b.set((4313, 103, 1500), "minecraft:composter")
    for p in ((4313, 105, 1496), (4315, 105, 1501)):
        b.set(p, "minecraft:lantern[hanging=true]")
    for p in ((4317, 103, 1484), (4308, 103, 1486), (4320, 103, 1490), (4309, 103, 1492)):
        b.set(p, "minecraft:lantern[hanging=true]")
    return b


# --------------------------------------------------------------------------------------- gym 5: Koga's fen sump
def gym5_commands(gym, recs):
    """The sump under the watch: a mud fen six blocks below a web of one-wide causeways, most of which stop."""
    b = Build()
    MB, PM = "minecraft:mud_bricks", "minecraft:packed_mud"
    b.comment("gym 5, Koga: the sump under the watch (data/gym_interiors.json gyms[gym5]).")
    b.comment("Koga's spawn-free box leaves four blocks east of the shell and two south: the most confined lot of the")
    b.comment("six, so the works are one room the size of the lot with the fen dug into its floor.")

    carve(b, gym, ["r1_sump", "c1_gate", "r2_hide", "c2_chute"])
    b.fill((4582, 109, 2485, 4582, 114, 2485), "minecraft:air", "the shaft through the rock between the sump and the shell")
    b.fill((4582, 115, 2485, 4582, 117, 2485), "minecraft:air", "the declared shell penetration")

    b.comment("-- the fen")
    b.fill((4574, 95, 2474, 4602, 95, 2492), PM, "its bed")
    b.fill((4574, 96, 2474, 4602, 96, 2492), "minecraft:mud",
           "and the mud itself. A fall from the causeways is six onto this, which costs a wade and nothing else "
           "(contract G3)")

    b.comment("-- the staging at either end")
    b.fill((4576, 102, 2482, 4584, 102, 2488), MB, "the entrance staging, under the shaft")
    b.fill((4598, 102, 2478, 4600, 102, 2482), MB, "the far staging")
    b.comment("-- the trackers' board of cast prints, which is the route, read before you start")
    b.fill((4576, 103, 2489, 4582, 105, 2489), "minecraft:mangrove_planks", "the board's face")
    for p in ((4577, 104, 2488), (4579, 104, 2488), (4580, 103, 2488), (4582, 104, 2488)):
        b.set(p, "minecraft:sculk")

    b.comment("-- the causeways that hold")
    for seg in ((4585, 2485, 4589, 2485), (4589, 2480, 4589, 2485), (4589, 2480, 4593, 2480),
                (4593, 2480, 4597, 2480), (4599, 2477, 4599, 2477), (4595, 2476, 4599, 2476),
                (4595, 2474, 4595, 2476), (4593, 2474, 4595, 2474)):
        b.fill((seg[0], 102, seg[1], seg[2], 102, seg[3]), MB)
    b.comment("-- and the ones that do not: each is a span that simply stops over the mud")
    for seg in ((4590, 2483, 4594, 2483), (4590, 2485, 4595, 2485),
                (4593, 2478, 4593, 2479), (4591, 2476, 4594, 2476), (4597, 2484, 4597, 2487),
                (4594, 2488, 4597, 2488)):
        b.fill((seg[0], 102, seg[1], seg[2], 102, seg[3]), MB)

    b.comment("-- the listening posts: the trackers' own, and not wired to anything")
    for p in ((4586, 97, 2478), (4592, 97, 2487), (4598, 97, 2474), (4580, 97, 2491)):
        b.set(p, "minecraft:sculk_sensor")
        b.set((p[0], 96, p[2]), "minecraft:sculk")

    b.comment("-- the fen ladder, the only way off the mud")
    b.fill((4574, 97, 2485, 4574, 103, 2485), MB, "its backing, built into the sump's west wall")
    b.fill((4575, 97, 2485, 4575, 103, 2485), "minecraft:ladder[facing=east]", "and the ladder")
    b.comment("its head steps straight east onto the staging, which is already there")

    b.comment("-- the shaft: scaffolding, because its lower half stands in the sump's own air")
    b.fill((4582, 103, 2485, 4582, 117, 2485), "minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]")

    b.comment("-- the hide")
    b.fill((4588, 102, 2466, 4598, 102, 2470), "minecraft:mangrove_planks", "its floor")
    b.fill((4589, 102, 2467, 4589, 102, 2467), "minecraft:air", "and the hole in it that is the way out")
    b.fill((4593, 102, 2471, 4594, 102, 2473), MB, "the gate's sill")
    b.fill((4590, 103, 2466, 4590, 105, 2466), "minecraft:mangrove_fence", "the reed racks")
    b.fill((4592, 103, 2466, 4592, 105, 2466), "minecraft:mangrove_fence")
    b.set((4596, 103, 2467), "minecraft:chest[facing=south]")
    for p in ((4595, 103, 2469), (4597, 103, 2469)):
        b.set(p, "minecraft:barrel[facing=up]")
    for p in ((4591, 105, 2468), (4596, 105, 2468), (4593, 105, 2470)):
        b.set(p, "minecraft:lantern[hanging=true]")
    for p in ((4578, 105, 2486), (4599, 105, 2480), (4589, 105, 2482), (4593, 105, 2477)):
        b.set(p, "minecraft:lantern[hanging=true]")
    return b


# ------------------------------------------------------------------------------------------ gym 7: Blaine's vent
def gym7_commands(gym, recs):
    """The throat: four vents in a floor, one of them open all the way to the quench pool, and a geyser back up
    that cannot be swum down."""
    b = Build()
    BB, BS = "minecraft:polished_blackstone_bricks", "minecraft:basalt"
    b.comment("gym 7, Blaine: the throat (data/gym_interiors.json gyms[gym7]).")
    b.comment("The lot is flat at y106 and there are 35 blocks of rock under it: the one gym in the six that is vertical.")

    carve(b, gym, ["r1_rim", "r2_throats", "c1_landing", "r4_galleries", "c3_stair", "r5_rack"])
    b.fill((6176, 102, 5003, 6176, 104, 5003), "minecraft:air", "the ladder shaft between the rim gallery and the shell")
    b.fill((6176, 105, 5003, 6176, 107, 5003), "minecraft:air", "the declared shell penetration")

    b.comment("-- floors")
    b.fill((6164, 95, 4993, 6178, 95, 5006), BB, "the rim gallery's and the throat chamber's floor, one course")
    b.fill((6168, 78, 4990, 6177, 78, 4997), BB, "the sample galleries' floor")
    b.fill((6169, 78, 4996, 6172, 78, 4999), BB, "the landing at the pool's north lip")
    b.fill((6173, 85, 4998, 6178, 85, 5006), BB, "the rack room's floor")

    b.comment("-- the wall between the rim gallery and the throat chamber, and the three-wide way through it")
    b.fill((6173, 96, 4997, 6173, 101, 5006), BB, "cut after the carve, because the two rooms' boxes meet")
    b.fill((6173, 96, 4998, 6173, 101, 5000), "minecraft:air", "the way through, which the researcher's reach closes")

    b.comment("-- the way down from the hall")
    b.fill((6176, 96, 5003, 6176, 107, 5003), "minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]",
           "scaffolding, as in every gym: its top cells stand inside the shell, whose blocks were never measured")

    b.comment("-- three throats that stop five down, each with a ladder back out")
    for (tx, tz) in ((6167, 4998), (6171, 4998), (6171, 5002)):
        b.fill((tx, 91, tz, tx + 1, 95, tz + 1), "minecraft:air", "a dry vent")
        b.fill((tx, 90, tz, tx + 1, 90, tz + 1), BS, "the cooled plug at its foot")
        b.fill((tx, 91, tz, tx, 95, tz), "minecraft:ladder[facing=east]",
               "and the way back out of it, carried by the uncut rock at x-1: a ladder in the hole's own air would "
               "have nothing behind it")

    b.comment("-- and the one that is open: eighteen of fall into six of water")
    b.fill((6167, 79, 5002, 6168, 95, 5003), "minecraft:air", "the cooled throat, all the way down")
    b.fill((6165, 72, 4999, 6170, 72, 5003), BB, "the quench pool's floor")
    b.fill((6165, 73, 4999, 6170, 78, 5003), "minecraft:water",
           "the pool: what makes the leap survivable at all (contract G3), and what is lit from below so the open "
           "throat can be told from the three dry ones before anyone steps off")
    for p in ((6166, 74, 5000), (6169, 74, 5002), (6166, 77, 5002)):
        b.set(p, "minecraft:lantern[hanging=false]")

    b.comment("-- the sample galleries: a three-wide working passage with one doorway at its west end")
    b.fill((6168, 79, 4990, 6177, 83, 4992), BS, "the gallery's south mass")
    b.fill((6168, 79, 4996, 6174, 83, 4996), BS, "and its north wall, so the landing does not open onto the whole of it")
    b.fill((6169, 79, 4996, 6170, 81, 4996), "minecraft:air",
           "the one doorway in from the landing. Everything east of it is behind the researcher")
    for p in ((6169, 79, 4993), (6174, 79, 4995), (6176, 79, 4993)):
        b.set(p, "minecraft:barrel[facing=up]")
    b.fill((6172, 79, 4995, 6173, 80, 4995), "minecraft:acacia_planks", "the core racks")

    b.comment("-- the climb to the rack room, seven up")
    b.fill((6175, 79, 4997, 6175, 86, 4997), BB, "its backing pier")
    b.fill((6176, 79, 4997, 6176, 86, 4997), "minecraft:ladder[facing=east]")

    b.comment("-- the rack room, and the wall the tap stands behind")
    b.set((6175, 86, 5000), "minecraft:cartography_table")
    b.set((6176, 86, 4999), "minecraft:brewing_stand")
    b.set((6174, 86, 5005), "minecraft:chest[facing=north]")
    b.fill((6173, 86, 5005, 6173, 87, 5006), "minecraft:terracotta", "crates of samples")
    b.fill((6173, 86, 5003, 6178, 90, 5003), BB, "the wall across the rack room")
    b.fill((6174, 86, 5003, 6176, 88, 5003), "minecraft:air", "and the three-wide gap the researcher stands in")
    for p in ((6175, 90, 5002), (6177, 90, 4999)):
        b.set(p, "minecraft:lantern[hanging=true]")

    b.comment("-- the geyser: soul sand under a water column, which carries you up ten and will not let you down it")
    b.fill((6178, 85, 5006, 6178, 85, 5006), "minecraft:soul_sand", "its source")
    b.fill((6177, 88, 5006, 6177, 95, 5006), BB, "its west wall")
    b.fill((6178, 88, 5005, 6178, 95, 5005), BB, "its south wall; the two open cells at its foot are the way in")
    b.fill((6178, 86, 5006, 6178, 95, 5006), "minecraft:water")
    b.fill((6178, 95, 5006, 6178, 95, 5006), "minecraft:water", "and the hole it makes in the rim gallery's floor")

    b.comment("-- light on the rim")
    for p in ((6175, 100, 5005), (6175, 100, 4998), (6166, 100, 4995), (6170, 100, 5005), (6165, 100, 5001)):
        b.set(p, "minecraft:lantern[hanging=true]")
    b.fill((6165, 96, 4994, 6165, 97, 4994), "minecraft:terracotta", "the instrument stands at the chamber's west end")
    return b


BUILDERS = {"gym1": gym1_commands, "gym2": gym2_commands, "gym3": gym3_commands,
            "gym4": gym4_commands, "gym5": gym5_commands, "gym7": gym7_commands}


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
        if gym["id"] not in BUILDERS:
            raise SystemExit("%s is marked built but this tool has no builder for it; gym 6 waits on EXP-034 and "
                             "gym 8 on its own unit (docs/mechanics/GYM_INTERIORS.md)" % gym["id"])
        rec = recs[gym["donor"]]
        (sx0, sy0, sz0), (sx1, sy1, sz1) = shell_box(rec)
        if [sx0, sy0, sz0, sx1, sy1, sz1] != gym["shell"]["expect_box"]:
            raise SystemExit("%s: the shell box derived from data/placements.json is %s but the record expects %s; "
                             "the placement moved and the interior must be re-fitted"
                             % (gym["id"], [sx0, sy0, sz0, sx1, sy1, sz1], gym["shell"]["expect_box"]))
        b = BUILDERS[gym["id"]](gym, recs)
        write_function(gym["id"], b.ops, set(gym["blocks"]))
        names.append(gym["id"])
        report["gyms"].append({
            "id": gym["id"], "donor": gym["donor"], "shell_box": [sx0, sy0, sz0, sx1, sy1, sz1],
            "dig": gym["dig"], "rooms": {r["id"]: r["box"] for r in gym["rooms"]},
            "commands": len([l for l in b.ops if not l.startswith("#")]),
            "entrance": gym["entrance"],
            "leader_spawner": list(to_world(rec, doc["measured"]["misty_relative" if gym["id"] == "gym2" else "small_gym_relative"]["trainer_spawner"])),
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
