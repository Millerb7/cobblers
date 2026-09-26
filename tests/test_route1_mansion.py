"""The Route 1 mansion (tools/route1_mansion.py) against the Gastly escort's scene and the house's Habitat Block.

Written by the test author, not by the session that wrote the builder or the scene.

What is asserted: replaying the house's earthwork commands (data/placements.json route1_mansion_house, through
tools/build_audit.replay, last write wins), every slot of every marker in scene route1_gastly_family is standable
(feet air or a thin block, head air, a solid block below) and every prop's `on` block is something the house writes;
the Habitat Block record route1_mansion_ward stands at WARD_STONE, where the house writes cobblemon:habitat_block,
its range reaches every interior floor cell of both storeys as a sphere, and its edge stays inside the forest's
mansion clearing. With the canonical heightmap present, the recorded commands are the ones the tool builds now.

The marker positions are hand-authored in data/scenes.json; the house is generated. Neither is derived from the other,
so this is a comparison of two independent sources.

Not covered, and it needs a running server: that an actor spawned at a marker actually stands (a Gastly floats; a
Gengar's hitbox is 1.3 x 1.8 and is only checked for the head block here); that ReplaceSpawns reaches as a sphere
(EXP-021 measured only the horizontal edge; the vertical shape is EXP-033, unrun); that the house stands in a world
as replayed (tools/town_audit.py on a staging export does that).
"""
import json
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_audit as BA  # noqa: E402
import maze_forest as MF  # noqa: E402
import route1_mansion as RM  # noqa: E402

PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
SCENE = next(s for s in json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))["scenes"]
             if s["id"] == "route1_gastly_family")
WARD = next(b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
            if b["id"] == "route1_mansion_ward")
DEFAULT_SLOTS = [[0.0, 0.0], [0.9, 0.0], [0.0, 0.9], [-0.9, 0.0]]     # tools/scenes_pack.py SLOTS
AIR = {"minecraft:air", "minecraft:cave_air"}
# a foot can stand in these: a carpet, fallen leaves, moss carpet, a candle, a trapdoor lying flat
THIN = ("_carpet", "minecraft:leaf_litter", "minecraft:candle", "_candle", "_trapdoor")
# the house's interior floor cells, as the task states them: x1617..1642, z5025..5042, feet at y115 and y121
INTERIOR_X, INTERIOR_Z, FEET_Y = range(1617, 1643), range(5025, 5043), (115, 121)


def thin(b):
    return b is not None and (b in AIR or b.endswith(THIN) or b == "minecraft:leaf_litter")


def solid(b):
    return b is not None and b not in AIR and not thin(b)


@pytest.fixture(scope="module")
def house():
    recs = [p for p in PLACEMENTS["placements"] if p["id"] == "route1_mansion_house"]
    assert len(recs) == 1, "data/placements.json must hold the house exactly once"
    cmds = recs[0]["commands"]
    assert len(cmds) > 1000, "the recorded house is (nearly) empty: nothing to check against"
    cols = {(x, z) for x in range(RM.X0 - 2, RM.X1 + 3) for z in range(RM.Z0 - 2, RM.Z1 + 3)}
    rep = BA.replay(cmds, cols)
    return lambda x, y, z: rep.get((x, z), {}).get(y)


def slots_of(name):
    m = SCENE["markers"][name]
    at = m["at"] if isinstance(m, dict) else m[:3]
    slots = (m.get("slots") if isinstance(m, dict) else None) or SCENE.get("slots") or DEFAULT_SLOTS
    for ox, oz in slots:
        yield name, (ox, oz), (math.floor(at[0] + 0.5 + ox), at[1], math.floor(at[2] + 0.5 + oz))


MARKER_SLOTS = [s for name in SCENE["markers"] for s in slots_of(name)]


# Without it an actor spawns inside a table, a wall or a step, or floats over the stairwell, and the escort's
# checkpoint puts Pip where nobody can reach or see him.
@pytest.mark.parametrize("name,slot,cell", MARKER_SLOTS, ids=["%s%s" % (n, list(s)) for n, s, _c in MARKER_SLOTS])
def test_every_marker_slot_is_standable_in_the_house(house, name, slot, cell):
    x, y, z = cell
    feet, head, below = house(x, y, z), house(x, y + 1, z), house(x, y - 1, z)
    assert thin(feet), "feet at %s: %s" % (cell, feet)
    assert head in AIR, "head at %s: %s" % ((x, y + 1, z), head)
    assert solid(below), "below %s: %s" % (cell, below)


# Without it a prop's click box hangs over bare floor or air, and the thing the dialogue describes is not there.
@pytest.mark.parametrize("prop", SCENE["props"], ids=[p["id"] for p in SCENE["props"]])
def test_every_prop_sits_on_something_the_house_builds(house, prop):
    got = house(*prop["on"])
    assert got is not None and got not in AIR, "%s on %s: %s" % (prop["id"], prop["on"], got)


# Without it the parametrised tests above could pass on an empty scene.
def test_the_scene_has_markers_and_props_to_check():
    assert len(MARKER_SLOTS) >= 20 and len(SCENE["props"]) >= 10


# Without it the Habitat Block R9E places and the stone the house sets in the landing floor could part company:
# the ward would sit somewhere else, or the house would overwrite it.
def test_the_ward_record_stands_where_the_house_writes_the_habitat_block(house):
    pos = (WARD["position"]["x"], WARD["position"]["y"], WARD["position"]["z"])
    assert pos == tuple(RM.WARD_STONE)
    assert house(*pos) == "cobblemon:habitat_block"


# Without it a corner of the house (a bedroom, the service corridor) falls outside the ward and back to the forest's
# pool, so a Caterpie spawns in the ballroom.
def test_the_ward_range_reaches_every_interior_floor_cell_as_a_sphere(house):
    assert (INTERIOR_X[0], INTERIOR_X[-1], INTERIOR_Z[0], INTERIOR_Z[-1]) == (RM.X0 + 1, RM.X1 - 1, RM.Z0 + 1, RM.Z1 - 1)
    assert FEET_Y == (RM.F + 1, RM.U + 1)
    wx, wy, wz = RM.WARD_STONE
    r = WARD["range_of_influence"]
    far = max(math.dist((x, y, z), (wx, wy, wz)) for x in INTERIOR_X for z in INTERIOR_Z for y in FEET_Y)
    assert far <= r, "farthest floor cell is %.2f from the ward, range %d" % (far, r)


# Without it the ghost pool reaches past the clearing into the forest, and ghosts spawn among the trees on Route 1's
# side path.
def test_the_ward_range_stays_inside_the_mansion_clearing():
    wx, _wy, wz = RM.WARD_STONE
    cx, cz = MF.MANSION
    edge = WARD["range_of_influence"] + math.hypot(wx - cx, wz - cz)
    assert edge <= MF.MANSION_CLEARING_R, "ward edge %.2f past the clearing's %d" % (edge, MF.MANSION_CLEARING_R)


# Without it data/placements.json holds a house the tool no longer builds (hand-edited, or the tool changed and was
# not re-run), and the checks above are about a house nobody will place.
def test_the_recorded_house_is_the_one_the_tool_builds():
    import ground as G
    import terrain as T
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the house's plinth depth comes from the canonical heightmap")
    try:
        g = G.Ground(root)
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)
    rec = next(p for p in PLACEMENTS["placements"] if p["id"] == "route1_mansion_house")
    assert rec["commands"] == RM.build(g)
