"""tools/rift_deep.py: the Windward Deep's chamber.

The Deep is carved 83 blocks under the Rift's floor, so the things worth asserting are the ones that would be
expensive or invisible to discover in game: that it cannot break the surface, that its region really is the
owner's tracing, and that nothing it places conditions a spawn.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_deep as D  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_deep.json").read_text(encoding="utf-8"))
REGIONS = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))
PLAN = ROOT / "derived" / "rift_deep" / "plan.json"


def _plan():
    if not PLAN.is_file():
        pytest.skip("the Deep has not been built")
    return json.loads(PLAN.read_text(encoding="utf-8"))


def test_the_floor_is_where_the_owner_put_it():
    # y0, not the y40 of the first sketch, and above the world's own floor with room for the shell.
    assert SPEC["floor_y"] == 0
    assert SPEC["floor_y"] - SPEC["form"]["shell"]["depth"] > -64, "the shell would reach through the world's floor"


def test_the_roof_can_never_break_the_surface():
    # The chamber is carved to a planned roof, but every column is clamped to leave min_cover of rock. Without the
    # clamp a shallow patch of the region would open the Deep to daylight.
    roof = SPEC["form"]["roof"]
    assert roof["min_cover"] >= 16
    ground_min = REGIONS["regions"]["the_deep"]["ground"]["min"]
    assert SPEC["floor_y"] + roof["centre"] + roof["min_cover"] <= ground_min, (
        "the planned roof plus its cover is higher than the lowest ground over the Deep (%d): every column there "
        "would be clamped, so the chamber would be flat rather than domed" % ground_min)


def test_the_audit_checks_the_rock_over_the_roof():
    # The shell closes the floor, not the ceiling. A natural cave meeting the roof would open the chamber to the
    # surface with nothing else noticing, so the audit samples the rock above it.
    src = (ROOT / "tools" / "rift_deep.py").read_text(encoding="utf-8")
    assert '"roof cover"' in src
    assert '"roof cover"' in src.split("def verify")[1], "verify does not require the roof-cover samples"
    p = _plan()
    kinds = {c[4] for c in p["checks"]}
    assert "roof cover" in kinds and sum(1 for c in p["checks"] if c[4] == "roof cover") > 50


def test_nothing_it_places_conditions_a_spawn():
    policy = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    used = set()
    for key in ("block", "fallback", "edge", "edge_fallback"):
        if key in SPEC["deck"]:
            used.add(SPEC["deck"][key])
    used.add(SPEC["light"]["block"])
    used.add(SPEC["light"]["fallback"])
    used.add(SPEC["form"]["shell"]["block"])
    used.add(SPEC["form"]["shell"]["fallback"])
    assert used and not (used & policy), used & policy


def test_the_decks_fit_inside_the_chamber():
    # An inset larger than the chamber's deepest point silently lays no deck at all.
    insets = [lv["inset"] for lv in SPEC["levels"]]
    assert insets == sorted(insets), "the decks must step inward"
    assert max(insets) < 109, "the chamber's deepest point is 109 from its wall"
    p = _plan()
    for lv in SPEC["levels"]:
        k = "deck columns (%s)" % lv["name"]
        assert p["counts"].get(k, 0) > 1000, "%s laid only %s columns" % (lv["name"], p["counts"].get(k))


def test_the_decks_are_not_walkable_between():
    # 16 blocks apart on purpose: the city moves by lift, which is what makes it read as built.
    ys = [lv["y"] for lv in SPEC["levels"]]
    for a, b in zip(ys, ys[1:]):
        assert b - a >= 8, "decks %d and %d are close enough to walk between" % (a, b)


def test_the_region_comes_from_the_pinned_image_not_a_scratch_file():
    src = (ROOT / "tools" / "rift_deep.py").read_text(encoding="utf-8")
    assert "sha256" in src and "floodfill" in src
    assert ".copy()" in src, "PIL floodfill is a silent no-op on a read-only array-backed image"
    assert "scratch" not in src.lower().replace("scratch directory", "")
