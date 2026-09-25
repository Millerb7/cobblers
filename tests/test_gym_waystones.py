"""The eight gym waystones in data/progression.json against where the towns place them, and the reconcile function
that follows them.

Written by the test author, not by the session that filled in the positions.

What is asserted: flags gym1_cleared..gym8_cleared each carry a waystone in gymN_town with an [x, y, z] position; x
and z are the town plan's waystone (data/placements.json settlements.<town>.plan.waystone.position, the independent
design record); y is the placed waystone's y in the town's placement report (derived/towns/<town>_placement.json
"waystone"), which also sits at the plan's x and z; and the generated reconcile (tools/progression_pack.files) holds,
for each gym, one activate and one forget line at exactly that position, and no "not placed" comment for any of them.

derived/ is gitignored: where a town's placement report is absent its y check SKIPs (a skip is not a pass).

Not covered, and it needs a running server: that `waystones activate/forget` at these coordinates reach the waystone
the town pass built (the block is where the report says), and that a player's unlocks follow the flag.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import progression_pack as PP  # noqa: E402

PROG = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
GYMS = ["gym%d" % i for i in range(1, 9)]
FLAGS = {f["id"]: f for f in PROG["flags"]}


def _ws(gym):
    return FLAGS["%s_cleared" % gym]["waystone"]


# Without it a gym flag loses its waystone (or one is left null) and every check below has nothing to compare.
@pytest.mark.parametrize("gym", GYMS)
def test_each_gym_flag_has_a_placed_waystone_in_its_town(gym):
    ws = _ws(gym)
    assert ws["town"] == "%s_town" % gym
    pos = ws["position"]
    assert isinstance(pos, list) and len(pos) == 3 and all(type(v) is int for v in pos), pos


# Without it the flag unlocks a waystone at a spot where none stands (the plan moved it and progression kept the old
# one), and a player who beat the gym still cannot travel there.
@pytest.mark.parametrize("gym", GYMS)
def test_a_gym_waystones_x_and_z_are_its_town_plans(gym):
    ws = _ws(gym)
    plan_ws = PLACEMENTS["settlements"][ws["town"]]["plan"]["waystone"]["position"]
    assert [ws["position"][0], ws["position"][2]] == list(plan_ws)


# Without it the y is a guess: activate at a block above or below the waystone finds no waystone and does nothing.
@pytest.mark.parametrize("gym", GYMS)
def test_a_gym_waystones_y_is_where_the_town_pass_placed_it(gym):
    ws = _ws(gym)
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % ws["town"])
    if not rep.is_file():
        pytest.skip("no %s (derived/ is gitignored; tools/place_town.py writes it)" % rep.relative_to(ROOT))
    placed = json.loads(rep.read_text(encoding="utf-8"))["waystone"]
    plan_ws = PLACEMENTS["settlements"][ws["town"]]["plan"]["waystone"]["position"]
    assert [placed[0], placed[2]] == list(plan_ws), "the town pass placed the waystone off its plan"
    assert ws["position"][1] == placed[1]


@pytest.fixture(scope="module")
def reconcile():
    files = PP.files(PP.plan(PP.load(ROOT / "data" / "progression.json"), None, PLACEMENTS))
    return files["data/%s/function/navigation/reconcile.mcfunction" % PROG.get("namespace", "cobblers")].splitlines()


# Without it the pack skips a gym's waystone (a "not placed" line) or activates it at other coordinates than the data,
# and the unlock silently never happens.
@pytest.mark.parametrize("gym", GYMS)
def test_reconcile_activates_and_forgets_each_gym_waystone_at_its_position(gym, reconcile):
    ws = _ws(gym)
    x, y, z = ws["position"]
    flag = "%s_cleared" % gym
    mine = [l for l in reconcile if ":flag/%s=" % flag in l]
    act = [l for l in mine if re.search(r" run waystones activate @s %d %d %d$" % (x, y, z), l)]
    forget = [l for l in mine if re.search(r" run waystones forget @s %d %d %d$" % (x, y, z), l)]
    assert len(act) == 1 and "%s=true" % flag in act[0], mine
    assert len(forget) == 1 and "%s=false" % flag in forget[0], mine
    assert len(mine) == 2, mine
    assert not [l for l in reconcile if l.startswith("# %s " % ws["town"]) and "not placed" in l]
