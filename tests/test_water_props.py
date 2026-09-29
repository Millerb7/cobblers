"""tools/route_events.py water_metrics()/water_prop_problems(): the Routes 1-3 water props still read their water.

Written by the test author, not by the session that wrote the check, the props or data/checks/water_props.json.

A water event's prop means something only in relation to the water beside it: a rod rack stands over the tidal
flat, a sounding staff stands on a named shelf, a muddy approach stops short of the pond. A reshaped heightmap
leaves the coordinates valid and the meaning wrong, which is what the 2026-09-28 water shape did to
route2_viltri_sounding's deep staff -- it rose a block and read the same depth as the middle staff, so the three
shelves stopped reading differently and dlg_route2_staff_deep's line stopped being true.

The positive test alone would prove nothing: a check that returns [] for every input also returns [] here, and a
step exiting 0 being read as content being right is exactly last night's bug. So the suite puts staff_deep back
at its pre-resite column (1708, 104, 3018) and requires BOTH failures it must produce, by name.

Ground is the canonical heightmap through tools/ground.py; no world is read (CLAUDE.md's ground rule).

NOT COVERED, and it needs a staging world or a server: that the props are actually built at these columns, that
the staff models stand in water rather than in a bank, that a player can reach them, and that the dialogue reads
true in play. This is arithmetic over a heightmap, not runtime behaviour.
"""
import copy
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import route_events as RE  # noqa: E402

CHECKS = json.loads((ROOT / "data" / "checks" / "water_props.json").read_text(encoding="utf-8"))
SCENES = {s["id"]: s for s in json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))["scenes"]}
WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
OLD_STAFF_DEEP = [1708, 104, 3018]     # where the deep staff stood before the 2026-09-29 re-site


@pytest.fixture(scope="session")
def ground():
    """The canonical heightmap, once. A skip is not a pass: it names what is missing."""
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def built_patch():
    """scene_patch()-shaped positions taken from data/scenes.json, so a test can move one prop and nothing else."""
    return {sid: {"props": {p["id"]: copy.deepcopy(p) for p in (s.get("props") or [])}}
            for sid, s in SCENES.items()}


def test_the_water_prop_check_is_not_vacuous():
    # If removed: water_prop_problems() could return [] because it has nothing to check, and every test below
    # would pass on an empty list.
    props = CHECKS["props"]
    assert len(props) == 11, "%d water props recorded, not the eleven Routes 1-3 build" % len(props)
    assert CHECKS["tolerance"]["depth"] == 0, "a depth tolerance above 0 lets a block of bed drift through"
    for want in props:
        scene = SCENES.get(want["scene"])
        assert scene, "%s is checked but no scene builds it" % want["scene"]
        ids = [p["id"] for p in scene.get("props") or []]
        assert want["prop"] in ids, "%s/%s is checked but the scene has no such prop" % (want["scene"], want["prop"])
        assert want["body"] in CHECKS["bodies"], "%s names water body %r, which has no level" % (
            want["prop"], want["body"])
    staffs = {w["prop"]: w for w in props if w["prop"].startswith("staff_")}
    assert staffs["staff_middle"]["deeper_than"] == ["staff_shallow"]
    assert staffs["staff_deep"]["deeper_than"] == ["staff_middle"], \
        "the deep staff no longer has to read deeper than the middle one: the sounding station means nothing"


def test_the_recorded_columns_are_the_columns_the_scenes_build():
    # If removed: data/checks/water_props.json could go on describing water beside columns no prop stands on.
    for want in CHECKS["props"]:
        p = next(q for q in SCENES[want["scene"]]["props"] if q["id"] == want["prop"])
        assert [p["on"][0], p["on"][2]] == want["column"], "%s/%s is built at (%d, %d) but measured at %s" % (
            want["scene"], want["prop"], p["on"][0], p["on"][2], want["column"])


def test_the_measurements_name_the_canonical_heightmap():
    # If removed: depths measured on a superseded heightmap would be trusted as current, which is the whole
    # failure mode this check exists for.
    assert CHECKS["measured_against"]["heightmap"] == WORLD["heightmap"]["sha256"], \
        "the water props were measured on a heightmap data/world.json no longer calls canonical"


@pytest.mark.slow
def test_recorded_depths_match_the_heightmap(ground):
    # Independent of water_metrics(): depth is the body's level minus the rounded ground under the prop's own
    # column. If removed: the recorded expectations could drift from the terrain and the check would enforce
    # numbers that describe nothing.
    for want in CHECKS["props"]:
        x, z = want["column"]
        got = CHECKS["bodies"][want["body"]] - ground(x, z)
        assert got == want["depth"], "%s/%s: the heightmap gives %d deep at (%d, %d), the record says %d" % (
            want["scene"], want["prop"], got, x, z, want["depth"])


@pytest.mark.slow
def test_every_water_prop_reads_the_water_it_was_sited_for(ground):
    # If removed: a reshaped bed could leave every prop's coordinates valid and its meaning wrong, as the
    # 2026-09-28 water shape did to the deep staff, with nothing failing.
    assert RE.water_prop_problems(ground) == []
    assert RE.water_prop_problems(ground, built_patch()) == [], "the built positions drift from data/scenes.json"


@pytest.mark.slow
def test_the_pre_resite_deep_staff_is_rejected_on_both_counts(ground):
    # THE NEGATIVE CASE. Without it the test above proves only that the function can return an empty list.
    # (1708, 3018) reads 6 deep, not the 7 the record is sited for, and the same 6 as staff_middle.
    patch = built_patch()
    patch["route2_viltri_sounding"]["props"]["staff_deep"]["on"] = OLD_STAFF_DEEP
    probs = RE.water_prop_problems(ground, patch)
    depth = [p for p in probs if p.startswith("route2_viltri_sounding/staff_deep:")]
    order = [p for p in probs if "no longer read differently" in p]
    assert depth, "the one-block depth drift was not reported: %s" % probs
    assert "6 deep under it, not the 7" in depth[0], depth[0]
    assert order, "the deep staff reading no deeper than the middle one was not reported: %s" % probs
    assert "staff_deep reads 6 deep and staff_middle reads 6" in order[0], order[0]
    assert len(probs) == 2, "expected exactly the two failures, got: %s" % probs


@pytest.mark.slow
def test_a_water_prop_that_stops_being_built_is_reported(ground):
    # If removed: deleting a prop would silence its check instead of failing it -- a check that disappears with
    # its content is not a check.
    patch = built_patch()
    del patch["route2_viltri_sounding"]["props"]["staff_deep"]
    probs = RE.water_prop_problems(ground, patch)
    assert any("staff_deep is expected but nothing builds it" in p for p in probs), probs


class FakeGround:
    """A 21 by 21 synthetic surface: dry at y70 everywhere except a pond at y60 in the columns x14-16, z9-11.

    Deterministic and hand-computable, so water_metrics() is tested on a surface whose answers are known rather
    than on the one real heightmap, where any return value looks plausible.
    """

    def __init__(self):
        import numpy as np
        self.heights = np.full((21, 21), 70.0)
        self.heights[9:12, 14:17] = 60.0
        self.ox = self.oz = 0

    def __call__(self, x, z):
        import numpy as np
        return int(np.round(self.heights[z, x]))

    def box(self, x0, z0, x1, z1):
        import numpy as np
        return np.round(self.heights[z0:z1 + 1, x0:x1 + 1]).astype(int)


def test_water_metrics_on_a_synthetic_surface_with_known_answers():
    # If removed: water_metrics() could compute depth or distance wrongly and every check built on it would
    # still agree with itself. At (10, 10), level 64: the ground is y70, so depth = 64 - 70 = -6 (dry land),
    # and the nearest column the water covers is (14, 10), exactly 4 blocks away.
    g = FakeGround()
    assert RE.water_metrics(g, 10, 10, 64, search=6) == (-6, 4.0)
    # inside the pond: the column is wet, so the waterline is 0 away and the water is 4 deep
    assert RE.water_metrics(g, 15, 10, 64, search=6) == (4, 0.0)
    # a diagonal: (12, 8) to the nearest wet column (14, 9) is hypot(2, 1)
    assert RE.water_metrics(g, 12, 8, 64, search=6) == (-6, 2.24)
    # and a search that cannot reach the water reports no waterline at all, never a distance of 0
    assert RE.water_metrics(g, 10, 10, 64, search=3) == (-6, None)


@pytest.mark.slow
def test_a_dry_prop_has_no_waterline_within_a_short_search(ground):
    # If removed: "no water within reach" could be silently read as "water right here". The lichen stones stand
    # 6.32 blocks from the pond, so a 3-block search must find none.
    stones = next(w for w in CHECKS["props"] if w["prop"] == "approach_stones")
    x, z = stones["column"]
    level = CHECKS["bodies"][stones["body"]]
    assert stones["waterline_distance"] > 3, "the fixture prop is nearer the water than the search below"
    assert RE.water_metrics(ground, x, z, level, search=3)[1] is None
