"""Measured town records: nearest_leg against data/routes.json polylines, and heights against the heightmap.

tools/validate_data.py measures what towns.json records instead of trusting it; tools/measure_towns.py writes the same
measurements back. These tests use synthetic routes and a synthetic height array, so they run without the source tree.

Not covered: the real heightmap (the repository test below only checks the route-derived fields, which need no
terrain), the tools/islet.py surface itself, and anything in game.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import measure_towns as M  # noqa: E402
import validate_data as V  # noqa: E402


def route(rid, frm, to, pts):
    poly, along = [], 0.0
    for i, (x, z) in enumerate(pts):
        if i:
            along += ((x - pts[i - 1][0]) ** 2 + (z - pts[i - 1][1]) ** 2) ** 0.5
        poly.append({"x": x, "y": 100, "z": z, "at_distance_blocks": along, "corridor_width_blocks": 64})
    return {"id": rid, "from_town": frm, "to_town": to, "corridor": {"polyline": poly}}


# two legs meeting at (1000, 0): a straight west-east leg, then a south leg
ROUTES = {"routes": [route("leg_a", "t0", "t1", [(0, 0), (1000, 0)]),
                     route("leg_b", "t1", "t2", [(1000, 0), (1000, 1000)])]}


def test_measure_nearest_leg_reports_route_fraction_and_point():
    # a centre 300 north of the middle of leg_a
    d, leg = V.measure_nearest_leg(ROUTES, {"x": 500, "z": -300})
    assert round(d) == 300
    assert leg == {"route_id": "leg_a", "from": "t0", "to": "t1", "at_fraction": 0.5, "nearest_point": {"x": 500, "z": 0}}


# removing the tie rule lets a centre nearest a shared town flip between the two legs from run to run
def test_tie_at_a_shared_town_goes_to_the_first_route():
    d, leg = V.measure_nearest_leg(ROUTES, {"x": 1300, "z": -300})
    assert leg["route_id"] == "leg_a" and leg["at_fraction"] == 1.0 and leg["nearest_point"] == {"x": 1000, "z": 0}


GOOD = {"route_id": "leg_a", "from": "t0", "to": "t1", "at_fraction": 0.5, "nearest_point": {"x": 500, "z": 0}}


def test_a_measured_record_has_no_problems():
    assert V._nearest_leg_problems(ROUTES, {"x": 500, "z": -300}, GOOD) == []


# each of these is a way towns.json was stale before this check existed; removing a clause lets that one through
@pytest.mark.parametrize("change,needle", [
    ({"nearest_point": {"x": 300, "z": 0}}, "not the nearest point"),          # moved route: old point, same leg
    ({"at_fraction": 0.2}, "at_fraction 0.2"),                                  # fraction from an older polyline
    ({"route_id": "leg_b", "from": "t1", "to": "t2"}, "nearest leg is"),        # a leg that is no longer nearest
    ({"from": "t9"}, "records t9->t1"),                                         # endpoints that do not match the route
    ({"route_id": None}, "has no polyline"),                                    # the short form without a route id
])
def test_stale_nearest_leg_is_reported(change, needle):
    rec = dict(copy.deepcopy(GOOD), **change)
    problems = V._nearest_leg_problems(ROUTES, {"x": 500, "z": -300}, rec)
    assert any(needle in p for p in problems), problems


def test_three_decimal_fraction_rounding_is_tolerated():
    rec = dict(GOOD, at_fraction=0.5004)
    assert V._nearest_leg_problems(ROUTES, {"x": 500, "z": -300}, rec) == []


def run_towns(tmp_path, towns):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / "world.json").write_text(json.dumps({"schema": "cobblers.world/1", "export": {"border": {
        "min_x": -5000, "min_z": -5000, "max_x": 5000, "max_z": 5000}}}), encoding="utf-8")
    (d / "progression.json").write_text(json.dumps({"schema": "cobblers.progression/1", "chapters": [], "flags": []}),
                                        encoding="utf-8")
    (d / "routes.json").write_text(json.dumps(ROUTES), encoding="utf-8")
    (d / "towns.json").write_text(json.dumps({"schema": "cobblers.towns/1", "towns": towns}), encoding="utf-8")
    ctx = V.Context(d, None, V.Report())
    V.check_schema(ctx)
    V.check_towns(ctx)
    return [f.message for f in ctx.report.findings if f.check == "towns" and f.severity == V.ERROR]


def outpost(nearest_leg):
    return {"id": "post", "role": "outpost", "tier": "outpost", "status": "proposed", "critical_path": False,
            "order": None, "gates": [], "centre": {"x": 500, "z": -300},
            "footprint": {"min_x": 490, "max_x": 510, "min_z": -310, "max_z": -290},
            "waystone": {"kind": "none"}, "distance_from_critical_path_blocks": 300, "nearest_leg": nearest_leg}


# removing the nearest_leg call from check_towns lets a stale record through the CLI check
def test_check_towns_reports_a_stale_nearest_leg(tmp_path):
    msgs = run_towns(tmp_path, [outpost(dict(GOOD, nearest_point={"x": 300, "z": 0}))])
    assert any('"post" nearest_leg is stale' in m for m in msgs), msgs
    assert not any("nearest_leg" in m for m in run_towns(tmp_path, [outpost(GOOD)]))


def test_measure_towns_refresh_rewrites_stale_route_fields():
    doc = {"towns": [dict(outpost({"from": "t0", "to": "t1", "at_fraction": 0.1}), distance_from_critical_path_blocks=250)]}
    changes = M.refresh(doc, ROUTES)
    t = doc["towns"][0]
    assert t["distance_from_critical_path_blocks"] == 300 and t["nearest_leg"] == GOOD
    assert {c[1] for c in changes} == {"distance_from_critical_path_blocks", "nearest_leg"}
    assert M.refresh(doc, ROUTES) == []   # idempotent


# ------------------------------------------------------------------ heights


def town_on(heights_fp, built=None):
    t = {"id": "t", "centre": {"x": 12, "z": 12, "ground_y": 0},
         "footprint": {"min_x": 10, "max_x": 14, "min_z": 10, "max_z": 14}}
    if built:
        t["built_ground"] = built
    return t


def test_measure_town_ground_reads_centre_range_and_slope():
    h = np.tile(np.arange(40, dtype=np.float32) + 100.0, (40, 1))   # a 1-in-1 ramp rising east
    m = V.measure_town_ground(h, {}, town_on(h))
    assert m["centre_ground_y"] == 112.0
    assert m["footprint_ground_y"] == [110.0, 114.0]
    assert abs(m["slope_mean"] - 45.0) < 0.01 and abs(m["slope_max"] - 45.0) < 0.01


# removing built_ground support measures Relic Island on its seabed again
def test_built_ground_is_laid_over_the_heightmap(monkeypatch):
    def raise_centre(win, x0, z0, world):
        win[12 - z0, 12 - x0] = 150.0
    monkeypatch.setitem(V.BUILT_GROUND, "tools/test_builder.py", raise_centre)
    h = np.full((40, 40), 35.0, dtype=np.float32)
    m = V.measure_town_ground(h, {}, town_on(h, "tools/test_builder.py"))
    assert m["centre_ground_y"] == 150.0 and m["footprint_ground_y"] == [35.0, 150.0]
    assert float(h[12, 12]) == 35.0       # the heightmap itself is not modified


# ------------------------------------------------------------- real data


# removing this lets data/towns.json nearest_leg records drift from data/routes.json unnoticed
def test_repository_nearest_legs_match_routes():
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
    stale = {t["id"]: V._nearest_leg_problems(routes, t["centre"], t["nearest_leg"])
             for t in towns if "nearest_leg" in t}
    assert {k: v for k, v in stale.items() if v} == {}
