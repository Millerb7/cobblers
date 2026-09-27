"""tools/town_dressing_audit.py's independence from tools/town_dressing.py, and the dressing's blocks against the spawn
conditions: the review tests/test_town_dressing.py (written by the implementing session) says is still owed.

Written by the test author, not by the session that built the dressing (143b23e).

Review of tests/test_town_dressing.py: its audit fixtures are synthetic plans with nonempty partial output, and they do
show each forbidden kind (lot, anchor, street, plaza, building, polyline verge, event site, clearing fill) is found.
What they cannot show: that the audit decides legality from plan data of its own and not from the generator (its mask
or its report), on the real plans; and the spawn check there runs each piece once with a constant hash, so a piece whose
variant blocks depend on its position, and the foundation courses (the town's `foundation`, else packed mud), are not
covered. This file adds those.

Independent sources: data/placements.json (streets, anchors, buildings), derived/towns/<town>_plan.json
(tools/town_plan.py: the house lots and street cells; a shared input of both tools, not the generator's output),
data/scenes.json (route event site areas), data/spawn_blocks.json (every block a spawn entry names), and
data/town_dressing.json.

The real-plan tests need derived/towns/<town>_plan.json for the five dressed towns (python tools/town_plan.py <town>);
without them they SKIP, and a skip is not a pass.

Not covered: a built pack against the real plans (tools/town_dressing.py build needs build/paint and derived/signposts,
absent here), anything in a world, and whether a piece reads as its town's purpose.
"""
from __future__ import annotations

import importlib
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import town_dressing as TD  # noqa: E402
import town_dressing_audit as TA  # noqa: E402

DATA = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
ALLOWED = set(DATA["blocks"]["ids"])
AUDIT_SRC = (ROOT / "tools" / "town_dressing_audit.py").read_text(encoding="utf-8")


def entries(town):
    t = DATA["towns"][town]
    out = ([dict(t["landmark"], id=t["landmark"].get("id", "landmark"))] if t.get("landmark") else []) \
        + list(t.get("pieces") or [])
    return [dict(e, foundation=e.get("foundation") or t.get("foundation")) if t.get("foundation") else e for e in out]


class Anywhere:
    """A generator mask that refuses nothing: the broken generation the audit must still catch."""

    def blocked(self, x, z):
        return None


def flat(y):
    return lambda x, z: y


# ------------------------------------------------------------------------------------------------ independence, source

# Without it the audit could quietly start trusting the generator (importing its Mask, reading its report under
# derived/town_dressing/), and a generator bug would pass its own check.
def test_the_audit_neither_imports_the_generator_nor_reads_its_report():
    assert not re.search(r"^\s*(import|from)\s+town_dressing\b", AUDIT_SRC, re.M)
    assert "import town_dressing " not in AUDIT_SRC and "town_dressing as" not in AUDIT_SRC
    assert '"derived" / "town_dressing"' not in AUDIT_SRC and "derived/town_dressing" not in AUDIT_SRC
    assert "Mask" not in AUDIT_SRC


@pytest.fixture
def audit_without_generator(monkeypatch):
    """The audit module re-imported with tools/town_dressing.py made unusable: any use of it raises."""
    poison = types.ModuleType("town_dressing")

    def refuse(name):
        raise AssertionError("the audit used the generator (town_dressing.%s)" % name)
    poison.__getattr__ = refuse
    monkeypatch.setitem(sys.modules, "town_dressing", poison)
    mod = importlib.reload(TA)
    yield mod
    monkeypatch.undo()
    importlib.reload(TA)


# ------------------------------------------------------------------------------------------------ a broken generation

def _plan(town):
    p = ROOT / "derived" / "towns" / ("%s_plan.json" % town)
    if not p.is_file():
        pytest.skip("no %s (python tools/town_plan.py %s)" % (p, town))
    return json.loads(p.read_text(encoding="utf-8"))


def _broken_function(town, spots):
    """The generator's own output for three of the town's pieces moved onto `spots`, with its mask switched off."""
    specs = [dict(e, at=list(at)) for e, at in zip(entries(town), spots)]
    cmds, report = TD.commands_for(town, specs, flat(135), Anywhere(), ALLOWED)
    return cmds, [s["id"] for s in specs]


# Without it the audit passes a generation that dressed a house lot, a street and a route event site, which is exactly
# the failure it exists for; checked on Brock's town's real plan, with the generator unusable while the audit runs.
def test_a_broken_generation_on_a_lot_a_road_and_an_event_site_is_refused(audit_without_generator):
    town = "gym1_town"
    plan = _plan(town)
    lot = plan["lots"][0]["rect"]
    road = PLACEMENTS["settlements"][town]["plan"]["streets"][0]["polyline"][1]            # a street's own vertex
    site = next(s["area"] for s in json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))["scenes"]
                if s["id"] == "route2_rollaway_geodude")
    spots = [((lot[0] + lot[2]) // 2, (lot[1] + lot[3]) // 2), tuple(road),
             ((site["from"][0] + site["to"][0]) // 2, (site["from"][2] + site["to"][2]) // 2)]
    cmds, ids = _broken_function(town, spots)
    TAx = audit_without_generator
    rects, _unknown = TAx.footprints(town, PLACEMENTS, _NoTemplates())
    probs = TAx.audit_town(town, cmds, plan, PLACEMENTS["settlements"][town]["plan"], rects, flat(135), SPAWN, ids,
                           TAx.event_sites())
    text = "\n".join(probs)
    assert re.search(r"%s: \d+ write\(s\) on lot " % re.escape(ids[0]), text), probs
    assert re.search(r"%s: \d+ write\(s\) on street" % re.escape(ids[1]), text), probs
    assert re.search(r"%s: \d+ write\(s\) on event site route2_rollaway_geodude" % re.escape(ids[2]), text), probs
    # and the same three pieces where the data puts them are not reported on any of those
    clean = TAx.audit_town(town, TD.commands_for(town, entries(town)[:3], flat(135), Anywhere(),
                                                 ALLOWED)[0],
                           plan, PLACEMENTS["settlements"][town]["plan"], rects, flat(135), SPAWN, ids,
                           TAx.event_sites())
    assert not [p for p in clean if " on lot " in p or " on street" in p or "event site" in p], clean


class _NoTemplates:
    """No template can be read here: the audit must say so rather than pass the building."""

    def get(self, q):
        return None, "not available in the test"


# Without it a building whose template cannot be read is simply left out of the check, and a piece written over it
# passes: the audit must name each such building (the fail-closed report main() prints).
def test_an_unreadable_building_template_is_reported_not_skipped():
    rects, unknown = TA.footprints("gym1_town", PLACEMENTS, _NoTemplates())
    templated = [q["id"] for q in PLACEMENTS["placements"] if q.get("settlement") == "gym1_town"
                 and q.get("kind") != "earthwork" and q.get("position") and not q.get("size")]
    assert templated and sorted(unknown) == sorted(templated)
    src = AUDIT_SRC[AUDIT_SRC.index("def main"):]
    assert "cannot read, so it is not checked" in src and "all_problems +=" in src


# ------------------------------------------------------------------------------------------------ spawn conditions

# Without it a piece whose blocks vary with its position (a hash of where it stands) could pick a spawn-condition
# block at one spot and not another: every piece, at its own spot, 40 other spots and every facing, writes only allowed
# blocks and no spawn condition.
def test_no_piece_writes_a_spawn_condition_at_any_spot_or_facing():
    bad, seen = [], set()
    for town in DATA["towns"]:
        for spec in entries(town):
            ox, oz = spec["at"]
            for k in range(41):
                for facing in TD.DIRS:
                    at = (ox + 17 * k, oz - 11 * k)
                    piece = TD.PIECES[spec["kind"]](dict(spec, facing=facing), lambda *v, a=at: TD.h32(a[0], a[1], *v))
                    for _x, _dy, _z, s in piece.blocks:
                        name = TD.block_name(TD.turn_state(s, facing))
                        seen.add(name)
                        if name in SPAWN or name not in ALLOWED:
                            bad.append((town, spec["id"], at, facing, name))
    assert len(seen) >= 20, sorted(seen)
    assert not bad, bad[:5]


# Without it the foundation course under a piece on falling ground (the town's `foundation`, else packed mud) is a
# spawn condition or outside the block list; checked on the generator's whole output for every town on steep ground.
@pytest.mark.parametrize("town", sorted(DATA["towns"]))
def test_the_whole_function_on_falling_ground_writes_no_spawn_condition(town):
    slope = lambda x, z: 100 + (x % 2)                     # noqa: E731 - relief 1, which every piece allows
    cmds, _ = TD.commands_for(town, entries(town), slope, Anywhere(), ALLOWED)
    names = {TD.block_name(m.group(1)) for c in cmds for m in [re.match(r"setblock -?\d+ -?\d+ -?\d+ (\S+)", c)] if m}
    fills = {TD.block_name(c.split()[7]) for c in cmds if c.startswith("fill ")}
    assert names and fills == {"minecraft:air"}, fills
    foundation = DATA["towns"][town].get("foundation") or "minecraft:packed_mud"
    assert foundation in names or not any(c.startswith("setblock") for c in cmds)
    assert not (names & SPAWN), sorted(names & SPAWN)
    assert names <= ALLOWED, sorted(names - ALLOWED)
    assert "minecraft:packed_mud" not in SPAWN and foundation not in SPAWN
