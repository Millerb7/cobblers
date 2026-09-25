"""The old mine's workings (tools/route1_old_mine.py MAIN, NORTH and SOUTH drifts and the STOPE) and the second find,
data/rewards.json r1_old_mine_stope.

Written by the test author, not by the session that extended the tool.

The replay, the world model, "standable" and the walk are tests/test_route1_old_mine.py's own (imported, not
re-derived): the recorded commands in data/placements.json replayed with tools/build_audit.replay, the canonical
heightmap (tools/ground.py, rounded) wherever they write nothing, and a walk from the notch outside the portal.

What is asserted: the stope's barrel is where r1_old_mine_stope says, inside its trigger box, and a walked cell stands
next to it inside that box; the walk reaches, below ground at the workings' floor, the end of the main drift and of
the north branch, and the foot of the south branch's fall of ground (by design rubble fills its last four blocks to
the roof, so the walk stops within three blocks of its end); every column of the workings keeps at least MIN_COVER
blocks of heightmap ground over its roof, where "roof" is found here by climbing from the drift floor through
see-through blocks in the replay (a hole to the sky would climb out and fail), not taken from the tool's own check;
the stope reward's items exist in Cobblemon 1.8.0 (assets/cobblemon/models/item/<id>.json in the jar).

The heightmap is outside the repository (COBBLERS_SOURCE_ROOT) and the Cobblemon jar is read from the EXP-000 runtime
copy (tools/battle_sim.JAR_CANDIDATES) or $COBBLERS_COBBLEMON_JAR, never from the live server tree; without them the
tests SKIP, and a skip is not a pass.

Not covered, and it needs a running server: that the workings stand as replayed on an export (tools/town_audit.py),
that the stope's advancement fires in its box and gives the cache once, the light the game computes in the drifts, and
what spawns in them.
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import route1_old_mine as OM  # noqa: E402
import test_route1_old_mine as M  # noqa: E402
from test_route1_old_mine import feet, ground, rep, walk, world  # noqa: E402,F401  (fixtures)

STOPE_REWARD = next(r for r in json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))["rewards"]
                    if r["id"] == "r1_old_mine_stope")


def _beside(at):
    x, y, z = at
    return [(x + a, y + e, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1) for e in (-1, 0, 1) if (a, b) != (0, 0)]


def _in_box(c, t):
    return all(t["min"][i] <= c[i] <= t["max"][i] for i in range(3))


# Without it the stope's barrel is built somewhere the reward does not know about, or its advancement's box is off the
# barrel, and the second find is scenery nobody is rewarded for reaching.
def test_the_stope_barrel_is_where_the_reward_says(rep):
    x, y, z = STOPE_REWARD["container"]["at"]
    assert STOPE_REWARD["container"]["block"] == "minecraft:barrel"
    assert rep[(x, z)].get(y) == "minecraft:barrel", rep[(x, z)].get(y)
    assert _in_box((x, y, z), STOPE_REWARD["trigger"])


# Without it the stope is sealed off or its trigger box is in rock: the drift is walked and the find at its end can
# neither be reached nor fire.
def test_a_walked_cell_stands_next_to_the_stope_barrel_inside_its_trigger_box(walk):
    assert len(walk) > 50
    beside = [c for c in _beside(STOPE_REWARD["container"]["at"]) if c in walk]
    assert beside, "no walked cell stands next to the stope's barrel"
    inside = [c for c in beside if _in_box(c, STOPE_REWARD["trigger"])]
    assert inside, "no walked cell next to the barrel is inside %s-%s" % (STOPE_REWARD["trigger"]["min"],
                                                                         STOPE_REWARD["trigger"]["max"])


def _floor(ground):
    # the workings are carved at the chamber's floor: the adit's floor (the ground at the portal) less the incline
    return ground(OM.PORTAL_X + 1, OM.Z_AXIS) - OM.DROP


def _underground(walk, ground):
    f = _floor(ground)
    return [c for c in walk if f + 1 <= c[1] <= f + 4]


# Without it a branch is cut off (a timber set across it, a step too high, rubble in the wrong place) and the copper
# face or the stope is drawn on the map and never reached; the walk on the surface above does not count.
@pytest.mark.parametrize("name,end,reach", [("main", OM.MAIN[-1], 0), ("north", OM.NORTH[-1], 0), ("south", OM.SOUTH[-1], 3)],
                         ids=["main", "north", "south"])
def test_each_branch_end_is_reached_by_the_walk_underground(walk, ground, name, end, reach):
    under = _underground(walk, ground)
    assert len(under) > 200, "almost nothing walked below ground: the check would pass on nothing"
    d = min(max(abs(c[0] - end[0]), abs(c[2] - end[1])) for c in under)
    assert d <= reach, "%s: the nearest walked cell below ground is %d blocks from its end %s" % (name, d, end)


def _workings_columns():
    """(x, z) of the drifts (3 wide round each centre line) and the stope, from the tool's design constants."""
    cols = set()
    for poly in (OM.MAIN, OM.NORTH, OM.SOUTH):
        for x, z, _ in OM.centre_line(poly):
            cols |= {(x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1)}
    sx, sz = OM.STOPE
    rx, rz = OM.STOPE_R
    for x in range(int(sx - rx) - 1, int(sx + rx) + 2):
        for z in range(int(sz - rz) - 1, int(sz + rz) + 2):
            if ((x - sx) / (rx * 1.1)) ** 2 + ((z - sz) / (rz * 1.1)) ** 2 <= 1:
                cols.add((x, z))
    return cols


# Without it a drift or the stope comes up under a thin skin of ground (or through it): a hole in the meadow west of the
# hill that a player falls into, and daylight in the mine.
def test_every_roof_the_workings_add_has_min_cover_of_heightmap_ground_above_it(world, ground):
    f = _floor(ground)
    checked, thin = 0, []
    for (x, z) in sorted(_workings_columns()):
        start = next((y for y in range(f + 1, f + 5) if world(x, y, z) in M.TRANSPARENT), None)
        if start is None:
            continue                                             # rubble or rock at the floor: nothing hollow here
        y = start
        while world(x, y, z) in M.TRANSPARENT and y < 320:
            y += 1
        roof = y
        checked += 1
        if ground(x, z) - roof < OM.MIN_COVER:
            thin.append(((x, z), roof, ground(x, z)))
    assert checked > 300, "only %d hollow columns found under the workings: the check would pass on nothing" % checked
    assert not thin, "%d columns with less than %d blocks of ground over the roof, e.g. %s" % (len(thin), OM.MIN_COVER,
                                                                                               thin[:5])


def _cobblemon_jar():
    import battle_sim
    cands = ([Path(os.environ["COBBLERS_COBBLEMON_JAR"])] if os.environ.get("COBBLERS_COBBLEMON_JAR") else []) \
        + list(battle_sim.JAR_CANDIDATES)
    for c in cands:
        if c.is_file():
            return c
    pytest.skip("no Cobblemon-fabric-1.8.0 jar outside the live server (EXP-000 runtime copy or $COBBLERS_COBBLEMON_JAR)")


# Without it the cache names an item that does not exist and the advancement's reward gives nothing (or fails to
# load).
def test_the_stope_rewards_items_are_cobblemon_items():
    items = [c["item"] for c in STOPE_REWARD["contents"]]
    assert items
    names = set(zipfile.ZipFile(_cobblemon_jar()).namelist())
    missing = [i for i in items if not i.startswith("cobblemon:")
               or "assets/cobblemon/models/item/%s.json" % i.split(":", 1)[1] not in names]
    assert not missing, missing
