"""Where a placed trainer stands against the building it stands in (tools/npc_spot_sweep.py).

The owner, 2026-10-04, flying staging: "the gym leader on a rock, the researcher in a wall, the mason on a roof, the
professor in a chimney -- those share a cause." The sweep replayed every block command the apply runs and found ONE
fault in the commands: all seven authored gym halls (data/gym_buildings/*.json, tools/gym_buildings.py) set the
leader's rctmod:trainer_spawner ON the floor, with its redstone in the floor course, so the leader -- spawned by RCT
at pos.above() -- stood one block above the floor on the spawner like a plinth. Every Cobbleverse gym template and the
League set theirs INTO the floor, the redstone under it.

These check the shared computation, not the data:
  - the transform the sweep turns a template with is the one /place template uses (tools/place_town.rotate, and
    tools/place_donor.box for a donor placed at its origin with a rotation)
  - spawner_problem(), the rule tools/gym_buildings.py now enforces, against hand-built floors, against the DONOR's
    own template (an expectation that comes from Cobbleverse, not from us), and against every hall's emitted text
    replayed independently of the generator's own model
  - a GENERATOR mutation (the spawner and its power written one block higher by Emit.set, the records untouched)
    is refused by the build
  - classify() on the shapes the owner named: a plinth, a roof, a chimney, a wall
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import npc_spot_sweep as S  # noqa: E402
import place_town as PT  # noqa: E402
import place_donor as PD  # noqa: E402
import gym_buildings as GB  # noqa: E402

ROTS = ("none", "clockwise_90", "180", "counterclockwise_90")
GYMS = sorted(p.stem for p in (ROOT / "data" / "gym_buildings").glob("*.json"))


class Grid:
    """A hand-built model: {(x, y, z): state}, air elsewhere."""

    def __init__(self, cells):
        self.cells = dict(cells)

    def at(self, x, y, z):
        return self.cells.get((x, y, z), "minecraft:air")

    def who(self, x, y, z):
        return "written" if (x, y, z) in self.cells else "terrain"


def floor(x0, x1, z0, z1, y, state="minecraft:stone_bricks"):
    return {(x, y, z): state for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


# ------------------------------------------------------------------------------------------------ the transform
@pytest.mark.parametrize("rot", ROTS)
def test_the_sweeps_transform_is_the_one_place_town_seats_with(rot):
    for x, z in ((0, 0), (5, 2), (18, 19), (3, 11)):
        assert S.transform(x, z, rot) == PT.rotate(x, z, rot), (rot, x, z)


@pytest.mark.parametrize("rot", ROTS)
def test_a_donor_turned_about_its_origin_lands_in_place_donors_box(rot):
    rec = {"position": {"x": 1000, "y": 64, "z": 2000}, "size": [27, 17, 24], "rotation": rot}
    lo, hi = PD.box(rec)
    sx, _sy, sz = rec["size"]
    cells = [S.transform(x, z, rot) for x in (0, sx - 1) for z in (0, sz - 1)]
    xs = [1000 + c[0] for c in cells]
    zs = [2000 + c[1] for c in cells]
    assert (min(xs), min(zs), max(xs), max(zs)) == (lo[0], lo[2], hi[0], hi[2]), rot


def test_mirror_is_applied_before_the_rotation():
    # StructureTemplate.transform: LEFT_RIGHT negates z, then the rotation turns the result
    assert S.transform(2, 3, "clockwise_90", "left_right") == (3, 2)
    assert S.transform(2, 3, "none", "front_back") == (-2, 3)


# ------------------------------------------------------------------------------------------------ the spawner rule
def test_a_spawner_set_into_the_floor_passes():
    g = floor(0, 4, 0, 4, 10)
    g[(2, 9, 2)] = "minecraft:redstone_block"
    g[(2, 10, 2)] = 'rctmod:trainer_spawner{TrainerIds:["kanto_brock"]}'
    assert S.spawner_problem(Grid(g).at, (2, 10, 2)) is None
    assert S.spawner_stand((2, 10, 2)) == (2, 11, 2)


def test_a_spawner_standing_on_the_floor_is_a_plinth():
    g = floor(0, 4, 0, 4, 10)
    g[(2, 10, 2)] = "minecraft:redstone_block"
    g[(2, 11, 2)] = 'rctmod:trainer_spawner{TrainerIds:["kanto_brock"]}'
    why = S.spawner_problem(Grid(g).at, (2, 11, 2))
    assert why and "stands proud of its floor" in why and "open on 4 side" in why


def test_a_spawner_against_a_wall_but_proud_of_the_floor_is_still_a_plinth():
    g = floor(0, 4, 0, 4, 10)
    for y in range(11, 14):
        g.update({(x, y, 4): "minecraft:stone_bricks" for x in range(0, 5)})
    g[(2, 11, 3)] = "rctmod:trainer_spawner"
    why = S.spawner_problem(Grid(g).at, (2, 11, 3))
    assert why and "open on 3 side" in why


def test_a_spawner_with_no_room_over_it_is_refused():
    g = floor(0, 4, 0, 4, 10)
    g[(2, 10, 2)] = "rctmod:trainer_spawner"
    g[(2, 12, 2)] = "minecraft:stone"
    why = S.spawner_problem(Grid(g).at, (2, 10, 2))
    assert why and "no room" in why


def _donor(tid):
    import town_character as TC
    T = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
    doc = T.from_archives("data/%s/structure/%s.nbt" % tuple(tid.split(":")))[0]
    if doc is None:
        pytest.skip("the Cobbleverse pack is not installed beside this checkout (%s)" % tid)
    pal = doc["palette"]
    return {tuple(b["pos"]): pal[b["state"]]["Name"] for b in doc["blocks"]}


@pytest.mark.parametrize("tid", ["cobbleverse:brock", "cobbleverse:erika", "cobbleverse:misty"])
def test_the_donor_gyms_set_their_spawner_into_the_floor(tid):
    # the expectation comes from Cobbleverse's own template, not from our records: the rule is what they do
    cells = _donor(tid)
    sp = [p for p, n in cells.items() if n == S.SPAWNER]
    assert len(sp) == 1, (tid, sp)
    at = lambda x, y, z: cells.get((x, y, z), "minecraft:air")  # noqa: E731
    assert S.spawner_problem(at, sp[0]) is None, (tid, sp[0])


# ------------------------------------------------------------------------------------------------ the gym halls
@pytest.mark.parametrize("gid", GYMS)
def test_every_hall_seats_its_leader_at_its_floors_level_in_the_generators_model(gid):
    doc = json.loads((ROOT / "data" / "gym_buildings" / ("%s.json" % gid)).read_text(encoding="utf-8"))
    e = GB.run_ops(doc, GB.ground_for(doc))
    sp = tuple(doc["leader"]["spawner"])
    assert S.spawner_problem(e.at, sp) is None, gid


@pytest.mark.parametrize("gid", GYMS)
def test_every_hall_seats_its_leader_at_its_floors_level_in_its_emitted_commands(gid):
    # replayed from the command text, with the sweep's own block model: not the generator's Emit model
    doc = json.loads((ROOT / "data" / "gym_buildings" / ("%s.json" % gid)).read_text(encoding="utf-8"))
    ground = GB.ground_for(doc)
    e = GB.run_ops(doc, ground)
    spawners = {}
    probe = S.Model(ground, [])
    S.replay_lines(probe, (("gym", c) for c in e.ops), spawners=spawners)
    assert len(spawners) == 1, (gid, spawners)
    (x, y, z), = spawners
    m = S.Model(ground, [(x - 3, y - 3, z - 3, x + 3, y + 4, z + 3)])
    S.replay_lines(m, (("gym", c) for c in e.ops))
    assert m.at(x, y, z).startswith(S.SPAWNER), gid
    assert S.spawner_problem(m.at, (x, y, z)) is None, gid
    cls, why = S.classify(m, *S.spawner_stand((x, y, z)))
    assert cls not in ("pedestal", "in_block", "no_floor", "enclosed"), (gid, cls, why)


def test_a_generator_that_lifts_the_spawner_off_the_floor_is_refused(monkeypatch):
    # MUTATE THE GENERATOR, not the record (CLAUDE.md): Emit.set writes the spawner and its power one block higher,
    # which is exactly what the seven halls did before 2026-10-04; data/gym_buildings/gym1.json is untouched
    doc = json.loads((ROOT / "data" / "gym_buildings" / "gym1.json").read_text(encoding="utf-8"))
    real = GB.Emit.set

    def lifted(self, pos, state):
        if state.startswith(S.SPAWNER) or state == "minecraft:redstone_block":
            pos = [pos[0], pos[1] + 1, pos[2]]
        return real(self, pos, state)
    monkeypatch.setattr(GB.Emit, "set", lifted)
    e = GB.run_ops(doc, GB.ground_for(doc))
    lot_rect, lot_level = GB.gym_lot(doc["settlement"])
    bad = GB.check_record(doc, lot_rect, lot_level, e)
    assert any("stands proud of its floor" in b for b in bad), bad


# ------------------------------------------------------------------------------------------------ the classes
def test_classify_names_the_shapes_the_owner_saw():
    base = floor(-3, 3, -3, 3, 10)
    # indoors: floor, room, roof
    g = dict(base)
    g.update(floor(-3, 3, -3, 3, 14, "minecraft:oak_planks"))
    assert S.classify(Grid(g), 0, 11, 0)[0] == "indoors"
    # outside: floor, nothing over it
    assert S.classify(Grid(base), 0, 11, 0)[0] == "outside"
    # a plinth: one block standing on the floor
    g = dict(base)
    g[(0, 11, 0)] = "rctmod:trainer_spawner"
    assert S.classify(Grid(g), 0, 12, 0)[0] == "pedestal"
    # on a roof: a written surface with a room under it and open sky over it
    g = dict(base)
    g.update(floor(-3, 3, -3, 3, 14, "minecraft:oak_planks"))
    assert S.classify(Grid(g), 0, 15, 0)[0] == "on_roof"
    # a chimney: a 1x1 hollow, solid all round
    g = dict(base)
    for y in (11, 12):
        for dx, dz in S.SIDES:
            g[(dx, y, dz)] = "minecraft:bricks"
    assert S.classify(Grid(g), 0, 11, 0)[0] == "enclosed"
    # in a wall
    g = dict(base)
    g[(0, 12, 0)] = "minecraft:stone_bricks"
    assert S.classify(Grid(g), 0, 11, 0)[0] == "in_block"
    # a pier's deck over the sea is not a roof
    g = floor(-3, 3, -3, 3, 64, "minecraft:spruce_planks")
    g.update(floor(-3, 3, -3, 3, 62, "minecraft:water"))
    g.update(floor(-3, 3, -3, 3, 61, "minecraft:sand"))
    assert S.classify(Grid(g), 0, 65, 0)[0] == "outside"


def test_the_sweep_reads_no_world():
    assert S.WORLD_READS == set()
    src = (ROOT / "tools" / "npc_spot_sweep.py").read_text(encoding="utf-8")
    assert "region_chunks" not in src and "level.dat" not in src
