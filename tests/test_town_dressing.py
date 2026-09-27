"""The town dressing: data/town_dressing.json, tools/town_dressing.py (the pieces) and tools/town_dressing_audit.py.

Written by the session that built the dressing, at the orchestrator's request; an independent test-author review is
still owed (CLAUDE.md: implementation does not grade its own work). The audit fixtures below are small plans with
nonempty partial output, so an audit that passed everything, or passed on nothing, fails here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import town_dressing as TD  # noqa: E402
import town_dressing_audit as TA  # noqa: E402

DATA = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
ALLOWED = set(DATA["blocks"]["ids"])


def specs():
    for sid, town in DATA["towns"].items():
        if town.get("landmark"):
            yield sid, dict(town["landmark"], id=town["landmark"].get("id", "landmark"))
        for q in town.get("pieces") or []:
            yield sid, q


def piece_blocks(spec):
    return [TD.block_name(s) for _x, _dy, _z, s in TD.PIECES[spec["kind"]](spec, lambda *v: TD.h32(1, 2, *v)).blocks]


def test_no_allowed_block_is_a_spawn_condition():
    # dressing must not decide what spawns in a town (TOWN_CENTERS.md rule 7): no whitelist covers it
    assert not ALLOWED & SPAWN, sorted(ALLOWED & SPAWN)


def test_every_piece_is_a_known_kind_and_writes_only_allowed_blocks():
    for sid, spec in specs():
        assert spec["kind"] in TD.PIECES, (sid, spec["id"], spec["kind"])
        blocks = set(piece_blocks(spec))
        assert blocks, (sid, spec["id"])
        assert blocks <= ALLOWED, (sid, spec["id"], sorted(blocks - ALLOWED))
        assert not blocks & SPAWN, (sid, spec["id"], sorted(blocks & SPAWN))


def test_every_dressed_town_has_a_landmark_a_purpose_and_pieces():
    assert DATA["towns"], "no town is dressed"
    for sid, town in DATA["towns"].items():
        assert town.get("purpose"), sid
        assert town.get("landmark") and town["landmark"].get("why"), sid
        assert len(town.get("pieces") or []) >= 5, sid


def test_piece_ids_are_unique():
    ids = [spec["id"] for _sid, spec in specs()]
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})


def test_turning_a_piece_turns_its_blocks_and_their_states():
    assert TD.turn_xz(0, -1, "north") == (0, -1)
    assert TD.turn_xz(0, -1, "east") == (1, 0)
    assert TD.turn_xz(0, -1, "south") == (0, 1)
    assert TD.turn_xz(0, -1, "west") == (-1, 0)
    assert TD.turn_state("minecraft:ladder[facing=south]", "east") == "minecraft:ladder[facing=west]"
    assert TD.turn_state("minecraft:oak_log[axis=x]", "west") == "minecraft:oak_log[axis=z]"
    assert TD.turn_state("minecraft:oak_log[axis=y]", "east") == "minecraft:oak_log[axis=y]"
    assert TD.turn_state("minecraft:spruce_fence[east=true,west=true]", "east") == "minecraft:spruce_fence[south=true,north=true]"
    assert TD.turn_state("minecraft:red_banner[rotation=0]", "south") == "minecraft:red_banner[rotation=8]"


def test_the_stilt_tower_ladder_leans_on_a_leg_and_arrives_at_an_open_edge():
    p = TD.PIECES["stilt_tower"]({"height": 10}, lambda *v: 0)
    at = {(x, dy, z): s for x, dy, z, s in p.blocks}
    for dy in range(0, 11):
        assert at[(1, dy, 2)].startswith("minecraft:ladder[facing=south]")
        assert "log" in at[(1, dy, 1)]                 # the leg it hangs on
    # somewhere beside the ladder's top the rail leaves a way onto the platform
    assert (0, 11, 2) not in at and "planks" in at[(0, 10, 2)]


# ------------------------------------------------------------------------------------------------ the plan audit
PLAN = {"lots": [{"id": "lot_a", "rect": [10, 10, 14, 14]}],
        "anchors": [{"id": "centre", "rect": [30, 10, 36, 16]}],
        "streets": {"main": {"cells": [[20, 64, 0, 40]]}},
        "plaza": {"rect": [40, 30, 44, 34]}}
PLAN_DATA = {"streets": [{"id": "main", "polyline": [[0, 20], [40, 20]], "width": 3}]}
BUILDINGS = {"house_1": (50, 0, 55, 5)}


def flat(_x, _z):
    return 64


def fn(*body, piece="p1"):
    return ["# generated", "forceload add 0 0 15 15", "# %s: crates (why)" % piece] + list(body)


def test_a_clean_function_passes():
    lines = fn("fill 2 65 2 3 67 3 minecraft:air replace #minecraft:replaceable", "setblock 2 65 2 minecraft:barrel[facing=up]",
               "setblock 3 65 3 minecraft:barrel[facing=up]")
    assert TA.audit_town("t", lines, PLAN, PLAN_DATA, BUILDINGS, flat, SPAWN, ["p1"]) == []


@pytest.mark.parametrize("line,what", [
    ("setblock 12 65 12 minecraft:barrel", "lot lot_a"),
    ("setblock 33 65 12 minecraft:barrel", "anchor lot centre"),
    ("setblock 5 65 20 minecraft:barrel", "street main"),
    ("setblock 42 65 32 minecraft:barrel", "plaza"),
    ("setblock 52 65 2 minecraft:barrel", "building house_1"),
    ("setblock 5 65 21 minecraft:barrel", "street (data polyline)"),      # beside the paving, inside the drawn width
    ("fill 8 65 9 11 66 11 minecraft:air replace #minecraft:replaceable", "lot lot_a"),   # a clearing fill counts too
])
def test_a_write_on_the_plan_is_found(line, what):
    lines = fn("setblock 2 65 2 minecraft:barrel", line)
    probs = TA.audit_town("t", lines, PLAN, PLAN_DATA, BUILDINGS, flat, SPAWN, ["p1"])
    assert any(what in p for p in probs), probs


def test_a_write_on_a_route_event_site_is_found():
    # Route 2's Geodude cart site stands just north of Brock's town; R12 builds it after the dressing
    lines = fn("setblock 2 65 2 minecraft:barrel", "setblock 61 65 61 minecraft:barrel")
    probs = TA.audit_town("t", lines, PLAN, PLAN_DATA, BUILDINGS, flat, SPAWN, ["p1"], [("geodude", (60, 60, 70, 70))])
    assert any("event site geodude" in p for p in probs), probs
    assert any(sid == "route2_rollaway_geodude" for sid, _r in TA.event_sites())


def test_an_empty_function_is_not_clean():
    assert TA.audit_town("t", ["# generated", "forceload add 0 0 15 15"], PLAN, PLAN_DATA, BUILDINGS, flat, SPAWN, [])


def test_a_listed_piece_that_is_not_written_is_found():
    probs = TA.audit_town("t", fn("setblock 2 65 2 minecraft:barrel"), PLAN, PLAN_DATA, BUILDINGS, flat, SPAWN, ["p1", "p2"])
    assert any("p2" in p and "not written" in p for p in probs), probs


def test_a_floating_or_buried_piece_is_found():
    probs = TA.audit_town("t", fn("setblock 2 70 2 minecraft:barrel"), PLAN, PLAN_DATA, BUILDINGS, flat, SPAWN, ["p1"])
    assert any("floats" in p for p in probs), probs
    probs = TA.audit_town("t", fn("setblock 2 60 2 minecraft:barrel"), PLAN, PLAN_DATA, BUILDINGS, flat, SPAWN, ["p1"])
    assert any("buried" in p for p in probs), probs


def test_a_spawn_condition_block_is_found():
    probs = TA.audit_town("t", fn("setblock 2 65 2 minecraft:bell"), PLAN, PLAN_DATA, BUILDINGS, flat, SPAWN, ["p1"])
    assert any("spawn condition" in p for p in probs), probs


def test_a_turned_template_footprint_swaps_its_sides():
    assert TA.turned_size([7, 5, 11], "none") == (7, 11)
    assert TA.turned_size([7, 5, 11], "clockwise_90") == (11, 7)
    assert TA.turned_size([7, 5, 11], "180") == (7, 11)
    assert TA.turned_size([7, 5, 11], "counterclockwise_90") == (11, 7)


# ------------------------------------------------------------------------------------------------ the re-apply step
def test_the_pack_is_installed_and_run_after_the_donors_and_the_lights():
    import reapply
    assert "cobblers_town_dressing" in reapply.SERVER_PACKS
    assert "cobblers_town_dressing" not in reapply.EXCLUDED
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.index('"R16B"') > src.index('("R16"') > src.index('("R9"')
    assert src.index("town_dressing_audit.py") > src.index('"town_dressing.py", "build"') > src.index('"signposts.py", "function"')


def test_the_built_pack_audits_clean_against_the_plans():
    """The real functions against the real plans, when this checkout has built them (reapply.py prepare)."""
    fdir = TD.FUNCS
    if not fdir.is_dir() or not all((fdir / ("%s.mcfunction" % s)).is_file() for s in DATA["towns"]):
        pytest.skip("cobblers_town_dressing is not built here (python tools/town_dressing.py build)")
    import os
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("COBBLERS_SOURCE_ROOT unset: no canonical heightmap here")
    if not all((ROOT / "derived" / "towns" / ("%s_plan.json" % s)).is_file() for s in DATA["towns"]):
        pytest.skip("the town plans are not built here (python tools/town_plan.py <town>)")
    assert TA.main([]) == 0
