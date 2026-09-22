"""Sightline tooling for the foliage pass: sightlines.cast(surface=...), landmark_trees.check, and
critical_legs.victory_road / legs.

Synthetic flat worlds with hand-placed canopy walls, plus one read of the real data/towns.json and
data/landmarks.json for the Victory Road polyline (no heightmap needed).

Not covered: whether a crown is actually visible in game (render distance, fog, Distant Horizons LODs, leaf
transparency), candidates() ranking, and routing quality of the A* legs on the real heightmap.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import critical_legs as CL  # noqa: E402
import landmark_trees as LT  # noqa: E402
import sightlines as SL  # noqa: E402


# ------------------------------------------------------------------ sightlines.cast surface

# removing this lets cast ignore the occluding surface (planned canopy never hides anything), or take observer and
# target heights from the canopy (an observer under trees would stand on the treetops)
def test_cast_occludes_on_surface_but_stands_on_heights():
    heights = np.zeros((64, 64), np.float32)
    surface = heights.copy()
    surface[:, 30:33] = 50.0            # a canopy wall across the line
    surface[32, 4:7] = 100.0            # canopy over the observer
    surface[32, 59:62] = 100.0          # and over the target
    target = {"x": 60, "z": 32}
    bare = SL.cast(heights, (5, 32), 2.0, target, 2.0)
    assert bare["visible"]
    r = SL.cast(heights, (5, 32), 2.0, target, 2.0, surface=surface, margin=2.0)
    assert not r["visible"]
    assert r["blocked_at"]["ground_y"] == 50.0 and 29.5 <= r["blocked_at"]["x"] <= 32.5
    assert r["observer_y"] == 2.0 and r["target_y"] == 2.0
    assert SL.cast(heights, (5, 32), 2.0, target, 2.0, surface=None) == bare


# ------------------------------------------------------------------ landmark_trees.check

def _check_fixture(glade=24):
    heights = np.zeros((256, 256), np.float32)
    surface = heights.copy()
    site = (128, 128)
    # the tree's own crown, as foliage.place stamps it into the canopy: 10 blocks round the trunk at y38
    surface[site[1] - 10:site[1] + 11, site[0] - 10:site[0] + 11] = 38.0
    doc = {"landmark_trees": [{"id": "t", "object": "lm", "site": list(site), "glade_radius": glade,
                               "seen_from": [{"kind": "ring", "radius": 60, "n": 8}]}]}
    lib = {"objects": [{"name": "lm", "group": "lm", "height": 40}]}
    return heights, surface, site, doc, lib


# removing this lets a landmark tree's own crown in the canopy grid hide the tree from every observer
def test_check_is_not_blinded_by_the_trees_own_crown():
    heights, surface, site, doc, lib = _check_fixture()
    ring = LT.ring_points(site, 60, 8)
    blind = LT.visibility(heights, surface, site, 40, ring)
    assert blind["visible"] == 0, "without removing the glade the crown blocks every ray (the fixture has teeth)"
    before = surface.copy()
    rows = LT.check(doc, heights, surface, {"legs": []}, lib)
    assert rows[0]["seen_from"][0]["observers"] == 8 and rows[0]["seen_from"][0]["visible"] == 8
    assert rows[0]["tree_height"] == 40 and rows[0]["crown_top_y"] == 40.0
    assert np.array_equal(surface, before), "the canopy is restored for the next landmark"


# removing this lets check() drop the whole canopy instead of only the landmark's glade, so real forest between
# the observer and the tree never blocks
def test_check_still_blocks_on_canopy_outside_the_glade():
    heights, surface, site, doc, lib = _check_fixture()
    zz, xx = np.mgrid[0:256, 0:256]
    r = np.hypot(xx - site[0], zz - site[1])
    surface[(r >= 36) & (r <= 40)] = 60.0           # a ring of tall forest outside the 24-block glade
    rows = LT.check(doc, heights, surface, {"legs": []}, lib)
    assert rows[0]["seen_from"][0]["visible"] == 0


# removing this lets leg observers be sampled off the named legs or at the wrong spacing
def test_leg_points_follow_named_legs_at_spacing():
    legs = {"legs": [{"from": "a", "to": "b", "polyline": [[0, 0], [100, 0], [100, 50]]},
                     {"from": "b", "to": "c", "polyline": [[500, 500], [600, 500]]}]}
    pts = LT.leg_points(legs, {"a->b"}, spacing=48)
    assert pts == [(0.0, 0.0), (48.0, 0.0), (96.0, 0.0), (100.0, 44.0)]


# ------------------------------------------------------------------ critical_legs

RIFT = {"landmarks": [{"id": "rift", "axes": [
    {"id": "trunk", "polyline": [[50, 0], [50, 40], [50, 80]]},                # apex first, fork last
    {"id": "south_west_arm", "polyline": [[50, 80], [20, 120], [0, 160]]},     # fork first, foot last
    {"id": "west_arm", "polyline": [[50, 60], [0, 60]]},
]}]}


# removing this lets Victory Road run the Rift backwards (apex to foot), skip the arm, or visit the fork twice
def test_victory_road_climbs_arm_then_trunk():
    a = {"centre": {"x": 0, "z": 200}}
    b = {"centre": {"x": 60, "z": -20}}
    vr = CL.victory_road(a, b, RIFT)
    assert vr == [[0, 200], [0, 160], [20, 120], [50, 80], [50, 40], [50, 0], [60, -20]]
    assert vr.count([50, 80]) == 1


# removing this lets a missing Rift or axis crash the leg builder instead of falling back to routing
def test_victory_road_needs_rift_arm_and_trunk():
    a, b = {"centre": {"x": 0, "z": 0}}, {"centre": {"x": 1, "z": 1}}
    assert CL.victory_road(a, b, {"landmarks": []}) is None
    no_arm = {"landmarks": [{"id": "rift", "axes": [RIFT["landmarks"][0]["axes"][0]]}]}
    assert CL.victory_road(a, b, no_arm) is None


# removing this lets the League leg be A*-routed like the others instead of following Victory Road
def test_legs_use_victory_road_only_for_the_league_leg():
    heights = np.full((256, 256), 100.0, np.float32)
    towns = {"towns": [
        {"id": "home", "tier": "critical", "role": "hometown", "order": 0, "centre": {"x": 20, "z": 20}},
        {"id": "gym", "tier": "critical", "role": "gym_town", "order": 1, "centre": {"x": 200, "z": 30}},
        {"id": "league", "tier": "critical", "role": "league", "order": 2, "centre": {"x": 60, "z": -20}},
        {"id": "outpost", "tier": "outpost", "role": "outpost", "centre": {"x": 100, "z": 100}},
    ]}
    rows = CL.legs(towns, heights, 62, RIFT)
    assert [(r["from"], r["to"]) for r in rows] == [("home", "gym"), ("gym", "league")]
    assert "victory_road" not in rows[0] and rows[0]["polyline"]
    vr = rows[1]
    assert vr["victory_road"] is True and vr["polyline"][0] == [200, 30] and vr["polyline"][-1] == [60, -20]
    p = np.array(vr["polyline"], float)
    assert vr["length_blocks"] == round(float(np.hypot(*np.diff(p, axis=0).T).sum()))


# removing this lets the real Victory Road (gym 8 town to the League up the Rift) change shape unnoticed
def test_real_victory_road_runs_from_gym8_up_the_rift_to_the_league():
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
    landmarks = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    crit = sorted([t for t in towns["towns"] if t.get("tier") == "critical"], key=lambda t: t["order"])
    a, b = crit[-2], crit[-1]
    assert b["role"] == "league"
    rift = next(l for l in landmarks["landmarks"] if l["id"] == "rift")
    ax = {x["id"]: x["polyline"] for x in rift["axes"]}
    vr = CL.victory_road(a, b, landmarks)
    assert vr[0] == [a["centre"]["x"], a["centre"]["z"]] and vr[-1] == [b["centre"]["x"], b["centre"]["z"]]
    assert vr[1] == ax["south_west_arm"][-1], "the road enters the Rift at the foot of the south-west arm"
    # the League stands on the trunk's floor below the apex (2026-09-21): the road follows the trunk to its point
    # nearest the League and stops, never running on to the apex and back
    assert vr[-2] in ax["trunk"] and vr[-2] != ax["trunk"][0], "and stops on the trunk short of the apex"
    assert ax["south_west_arm"][0] == ax["trunk"][-1], "arm and trunk meet at the fork"
    assert vr.count(ax["trunk"][-1]) == 1
    length = sum(math.dist(p, q) for p, q in zip(vr, vr[1:]))
    assert round(length) == 4283
