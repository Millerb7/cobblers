"""Bridges (data/bridges.json, tools/bridges.py): the offline audit fails each way a bridge can be wrong.

The fixtures are a synthetic valley, not the heightmap, so these run in any checkout: flat ground at y70, a channel
across rows 10-14 with its bed at y64 and water at 69. The generator's own plan must audit clean, and each defect
put into its function (a missing deck row, a cut-short ramp, a block in the water, water itself, a low beam, a
floating lantern, a town beside it, a pier across a step in the water) must fail the check that names it. The real
crossing is audited against the canonical heightmap when it is present (COBBLERS_SOURCE_ROOT).

Written by the implementing agent (world-content-dev) because the task asked for the audit with the bridge; an
independent test-author review of these fixtures is still owed (CLAUDE.md: implementation does not grade itself).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bridges as B  # noqa: E402

BOX = (0, 0, 30, 40)
DEFAULTS = {"clearance_air_blocks": 3, "ramp_fall_per_row": 0.5, "headroom_blocks": 4, "max_post_spacing_rows": 8,
            "town_margin_blocks": 16}
MATERIALS = json.loads((ROOT / "data" / "bridges.json").read_text(encoding="utf-8"))["bridges"][0]["materials"]
NO_TOWNS = {"towns": []}
NO_PLACEMENTS = {"settlements": {}, "placements": []}


def valley(step=False):
    """(ground callable, level, wet, definite) over BOX. With `step`, the channel's east half stands a block lower,
    as a lake's outflow stands under the lake."""
    shape = (BOX[3] - BOX[1] + 1, BOX[2] - BOX[0] + 1)
    g = np.full(shape, 70, int)
    g[10:15, :] = 64
    level = np.zeros(shape, int)
    level[10:15, :] = 69
    if step:
        level[10:15, 16:] = 68
    wet = level > g
    definite = wet.copy()
    return (lambda x, z: int(g[z, x])), level, wet, definite


def bridge(piers=None):
    return {"id": "fixture", "working_name": "fixture", "route": "fixture_route", "axis": "z", "centre": 15,
            "along_from": 0, "along_to": 40, "walkway_half_width": 1, "crossing": {"waypoint": [15, 12]},
            "piers": piers if piers is not None else [{"from": 12, "to": 12}], "materials": MATERIALS}


def lines_for(b, step=False):
    ground, level, wet, definite = valley(step)
    p = B.plan(b, DEFAULTS, ground, level, wet, definite, BOX)
    return p, B.commands(p, b)


def run(b, lines, step=False, towns=NO_TOWNS, placements=NO_PLACEMENTS):
    ground, level, wet, definite = valley(step)
    return {name: (ok, detail) for name, ok, detail in
            B.audit_bridge(b, DEFAULTS, lines, ground, level, wet, definite, BOX, towns, placements)}


def failed(res):
    return sorted(k for k, (ok, _d) in res.items() if not ok)


def test_the_plan_audits_clean_and_is_not_empty():
    b = bridge()
    p, lines = lines_for(b)
    res = run(b, lines)
    assert not failed(res), res
    r = p["report"]
    assert r["water_rows"] == [10, 14] and r["deck_y"] == 69 + 1 + 3
    # ramps fall half a block a row from the abutments (rows 9 and 15) to ground at y70 (surface 71)
    assert r["feet"] == [4, 20]
    assert r["lanterns"] >= 4
    assert "rows 4-20 walkable" in res["deck continuous bank to bank"][1]


def test_an_empty_function_fails_closed():
    res = run(bridge(), ["# nothing", "forceload add 0 0 1 1"])
    assert failed(res) == ["nonempty"]


def test_a_missing_deck_row_breaks_the_deck():
    b = bridge()
    _p, lines = lines_for(b)
    cut = [l for l in lines if not (l.startswith(("setblock", "fill")) and l.split()[3] == "11" and "air" not in l)]
    assert len(cut) < len(lines)
    assert "deck continuous bank to bank" in failed(run(b, cut))


def test_a_ramp_cut_short_does_not_meet_the_ground():
    b = bridge()
    _p, lines = lines_for(b)
    far = {"4", "5", "6"}                                   # the north ramp's last three rows
    cut = [l for l in lines if not (l.startswith(("setblock", "fill")) and l.split()[3] in far)]
    assert "ends meet the heightmap ground within one block" in failed(run(b, cut))


def test_a_block_in_the_water_outside_the_piers_fails():
    b = bridge()
    _p, lines = lines_for(b)
    assert "water untouched but for the piers" in failed(run(b, lines + ["setblock 15 66 10 minecraft:stone_bricks"]))


def test_air_in_the_water_counts_as_removing_it():
    b = bridge()
    _p, lines = lines_for(b)
    assert "water untouched but for the piers" in failed(run(b, lines + ["fill 14 65 13 16 69 13 minecraft:air"]))


def test_placing_water_fails_even_above_the_level():
    b = bridge()
    _p, lines = lines_for(b)
    assert "water untouched but for the piers" in failed(run(b, lines + ["setblock 15 90 12 minecraft:water"]))


def test_a_light_block_fails():
    b = bridge()
    _p, lines = lines_for(b)
    assert "water untouched but for the piers" in failed(run(b, lines + ["setblock 15 76 12 minecraft:light"]))


def test_a_beam_under_the_deck_takes_the_clearance():
    b = bridge()
    _p, lines = lines_for(b)
    assert "clearance over the water" in failed(run(b, lines + ["setblock 15 71 11 minecraft:spruce_log"]))


def test_a_floating_lantern_fails():
    b = bridge()
    _p, lines = lines_for(b)
    assert "lanterns on posts" in failed(run(b, lines + ["setblock 15 79 11 minecraft:lantern[hanging=false]"]))


def test_a_town_lot_beside_the_bridge_fails():
    b = bridge()
    _p, lines = lines_for(b)
    towns = {"towns": [{"id": "t", "footprint": {"min_x": 25, "min_z": 0, "max_x": 30, "max_z": 5}}]}
    assert "clear of every town lot" in failed(run(b, lines, towns=towns))
    placements = {"settlements": {}, "placements": [{"id": "house", "position": {"x": 2, "z": 30}}]}
    assert "clear of every town lot" in failed(run(b, lines, placements=placements))


def test_a_pier_across_a_step_in_the_water_fails():
    b = bridge(piers=[{"from": 12, "to": 12}])            # the pier spans x14-16, and the step is at x15/16
    _p, lines = lines_for(b, step=True)
    assert "each pier in one water level" in failed(run(b, lines, step=True))


def test_the_plan_refuses_a_pier_off_the_water():
    with pytest.raises(SystemExit):
        lines_for(bridge(piers=[{"from": 20, "to": 20}]))


def test_the_parser_refuses_what_it_cannot_audit():
    res = run(bridge(), ["fill 0 70 0 1 70 1 minecraft:stone keep"])
    assert failed(res) == ["parse"]
    res = run(bridge(), ["execute run setblock 0 70 0 minecraft:stone"])
    assert failed(res) == ["parse"]


def test_the_data_names_its_route_and_a_crossing_on_it():
    doc = json.loads((ROOT / "data" / "bridges.json").read_text(encoding="utf-8"))
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
    ids = {r["id"] for r in routes["routes"]}
    assert doc["schema"] == "cobblers.bridges/1" and doc["bridges"]
    for b in doc["bridges"]:
        assert b["route"] in ids
        wp = routes["routing"]["mandatory_waypoints"].get(b["route"], {}).get("points") or []
        assert list(b["crossing"]["waypoint"]) in [list(p) for p in wp], "the bridge is not on its route's waypoint"


def _heightmap():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT is not set: the canonical heightmap is outside the repo")
    import ground as GR
    import terrain as T
    try:
        return GR.Ground(root)
    except T.TerrainUnavailable as e:  # the heightmap missing, or not the one data/world.json pins
        pytest.skip("canonical heightmap not available: %s" % e)


def test_the_route7_bridge_audits_clean_on_the_canonical_heightmap():
    g = _heightmap()
    doc = B.load()
    b = next(x for x in doc["bridges"] if x["id"] == "route7_tilpey_outflow")
    box = B.window(b)
    level, wet, definite = B.water(g.heights, g.world, box)
    p = B.plan(b, doc["defaults"], g, level, wet, definite, box)
    res = {n: (ok, d) for n, ok, d in B.audit_bridge(b, doc["defaults"], B.commands(p, b), g, level, wet, definite, box,
                                                    B.load("towns.json"), B.load("placements.json"))}
    assert not failed(res), res
    r = p["report"]
    assert r["walkway_blocks"] == 5 and r["top_water_y"] == 77 and r["deck_y"] == 81
    assert r["water_rows"][0] < 3904 + 10 and r["water_rows"][1] > 3904


def test_the_reapply_driver_builds_every_bridge_after_the_towns_and_before_the_lights(monkeypatch):
    import reapply
    # steps() lists other packs' functions from their built index files; this checkout need not have them
    monkeypatch.setattr(reapply, "indexed", lambda pack, folder: [])
    steps = reapply.steps()
    ids = [s[0] for s in steps]
    assert "R9G" in ids
    assert ids.index("R8") < ids.index("R9") < ids.index("R9G") < ids.index("R16")
    fns = [v for k, v in dict((s[0], s[2]) for s in steps)["R9G"] if k == "fn"]
    doc = json.loads((ROOT / "data" / "bridges.json").read_text(encoding="utf-8"))
    assert fns == ["cobblers:bridges/%s" % b["id"] for b in doc["bridges"]] and fns
    assert "cobblers_bridges" in reapply.SERVER_PACKS
    assert "cobblers_bridges" not in reapply.EXCLUDED and "cobblers_bridges" not in reapply.WORLD_LOCAL
    # and prepare fails closed on the pack without its step
    todo = [s for s in steps if s[0] != "R9G"]
    fake = [("R9G", "", [("fn", f) for f in fns])]
    assert reapply.uncovered(todo + fake) == [] or all("cobblers_bridges" not in m for m in reapply.uncovered(todo + fake))
    if (reapply.PACKS / "cobblers_bridges" / "data").is_dir():
        assert any("cobblers_bridges" in m for m in reapply.uncovered(todo))
