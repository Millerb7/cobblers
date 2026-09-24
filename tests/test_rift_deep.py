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
    assert SPEC["floor_y"] - SPEC["shell"]["depth"] > -64, "the shell would reach through the world's floor"


def test_the_pit_is_open_to_the_sky():
    """The Deep is the Rift's deepest point, not a second Displaced City.

    Schema 1 put a domed roof on it, reasoning that 83 blocks down has ground overhead. That was circular: the
    ground is only overhead if the pit is not dug through it (owner, 2026-09-23). An open pit that is not open is
    the whole failure, so the audit samples every column at the old ground line and requires air.
    """
    assert SPEC["form"]["open_to_sky"] is True
    src = (ROOT / "tools" / "rift_deep.py").read_text(encoding="utf-8")
    assert '"open to the sky"' in src.split("def verify")[1], "verify does not require the open-to-sky samples"
    carve = src.split("def build")[1].split("def write")[0]
    for gone in ('roof["centre"]', 'roof["edge"]', "min_cover", '"roof cover"'):
        assert gone not in carve, "the carve still computes a roof: %s" % gone
    p = _plan()
    kinds = {c[4] for c in p["checks"]}
    assert "open to the sky" in kinds and sum(1 for c in p["checks"] if c[4] == "open to the sky") > 50


def test_everything_under_a_tread_is_rock():
    # Schema 1's chamber reached y22-52, which in the outer rings is BELOW the new tread at y66. Re-running over
    # it without refilling would leave each street a thin shelf over that void.
    src = (ROOT / "tools" / "rift_deep.py").read_text(encoding="utf-8")
    assert "replace #cobblers:rift_void" in src
    p = _plan()
    assert p["counts"].get("columns refilled under their tread", 0) == p["columns"]


def test_nothing_it_places_conditions_a_spawn():
    policy = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    used = set()
    for key in ("block", "fallback", "edge", "edge_fallback"):
        if key in SPEC["tread"]:
            used.add(SPEC["tread"][key])
    for sec in ("light", "shell", "restore", "lifts"):
        for key in ("block", "fallback"):
            if key in SPEC[sec]:
                used.add(SPEC[sec][key])
    assert used and not (used & policy), used & policy


def test_the_rings_are_the_city_and_nothing_competes_with_them():
    """One structure, not two.

    Schema 1 also had decks at y0, y16 and y32. Against these treads y32 coincides exactly and y16 sits one block
    off y15: two systems doing one job, and platforms floating in the middle read as a chamber's mezzanines
    (owner, 2026-09-23). The decks are gone.
    """
    assert "levels" not in SPEC and "deck" not in SPEC, "the decks are back, competing with the rings"
    rings = SPEC["rings"]
    assert rings["count"] == len(rings["treads"]) == 5
    p = _plan()
    for k, y in enumerate(rings["treads"]):
        key = "tread columns (ring %d, y%d)" % (k, y)
        assert p["counts"].get(key, 0) > 1000, "%s laid only %s columns" % (key, p["counts"].get(key))


def test_no_ring_can_be_climbed_back_up():
    # A 17-block riser is why the lifts are the only way between rings, and so why the tunnel still matters.
    treads = SPEC["rings"]["treads"]
    for a, b in zip(treads, treads[1:]):
        assert a - b >= 8, "rings %d and %d are close enough to climb between" % (a, b)
    p = _plan()
    assert p["counts"].get("lift pairs", 0) >= 4, "fewer lift pairs than ring boundaries: a ring is unreachable"


def test_the_traced_region_has_no_holes_left_in_it():
    """The owner's annotation writes each region's name across it in the same black as the outlines.

    A flood fill stops at the letters, so they survive as islands inside the region; carved, that left
    "the deep (town)" standing in rock in the middle of the chamber, which is how it was found -- on the owner's
    own map, after the build (2026-09-22). Every region was affected: 18,285 columns of lettering across eleven.
    """
    import os
    import numpy as np
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT unset")
    try:
        m, _, n = D.region_mask("the_deep", root)
    except D.DeepError as e:
        pytest.skip(str(e))
    from collections import deque
    h, w = m.shape
    out = np.zeros_like(m)
    q = deque()
    for i in range(w):
        for z in (0, h - 1):
            if not m[z, i] and not out[z, i]:
                out[z, i] = True
                q.append((z, i))
    for j in range(h):
        for x in (0, w - 1):
            if not m[j, x] and not out[j, x]:
                out[j, x] = True
                q.append((j, x))
    while q:
        z, x = q.popleft()
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nz, nx = z + dz, x + dx
            if 0 <= nz < h and 0 <= nx < w and not m[nz, nx] and not out[nz, nx]:
                out[nz, nx] = True
                q.append((nz, nx))
    assert int((~m & ~out).sum()) == 0, "the traced region still has holes: its label text would be carved as rock"


def test_the_recorded_column_count_is_the_filled_one():
    r = REGIONS["regions"]["the_deep"]
    assert "columns_with_label_holes" in r, "the pre-fill count is not kept, so the correction is invisible"
    assert r["columns"] > r["columns_with_label_holes"]


def test_the_region_comes_from_the_pinned_image_not_a_scratch_file():
    src = (ROOT / "tools" / "rift_deep.py").read_text(encoding="utf-8")
    assert "sha256" in src and "floodfill" in src
    assert ".copy()" in src, "PIL floodfill is a silent no-op on a read-only array-backed image"
    assert "scratch" not in src.lower().replace("scratch directory", "")
