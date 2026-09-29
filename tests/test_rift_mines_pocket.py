"""The dig camp's reshape: the quarries are cut from the shape of the pocket, and the camp can still walk out of it.

The owner, docs/world-building/SOUTHERN_RIFT_MEGA.md section 13: the camp "should also conform to the shape of the
pocket it is in, the quarry should be large and a little deep taking half of the area probably, with the strip mines
and stuff on top". data/rift_mines.json `pocket` says how that shape is measured (the canonical heightmap, never a
world) and tools/rift_mines_audit.py `pocket_problems` checks the traced cuts against it.

What is asserted here, without the heightmap (a fake ground stands in for it, so the checks themselves are tested
rather than today's terrain):
  - a traced cut whose outline leaves the pocket is reported, and one inside it with its inset is not;
  - a quarry that seals the pocket off from the seam yard is reported: the causeway between the two cuts is the thing
    that check exists for;
  - a street or a house inside a quarry is reported;
  - the generator and the audit rasterise the same footprint for every traced and trench cut in the committed data
    (two implementations of the data's `geometry` words), and the committed outlines are simple rings.
tools/rift_mines_audit.py run against the real heightmap is the check that the committed data passes; this file is
about the check, not about the terrain.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_mines as RM  # noqa: E402
import rift_mines_audit as RA  # noqa: E402

SPEC = json.loads((ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))


class _Grid:
    x0, x1, z0, z1, y0, y1 = 0, 79, 0, 79, 0, 127


def _ground(x, z):
    """A square basin: y80 inside x8..71 / z8..71, rising to y120 outside it."""
    return 80 if 8 <= x <= 71 and 8 <= z <= 71 else 120


def _spec(outline, streets=None, houses=None, seam=(30, 10, 40, 16)):
    sx0, sz0, sx1, sz1 = seam
    return {
        "pocket": {"seed": [40, 40], "floor_y": 90, "inset": 4,
                   "measured": {"columns": 64 * 64}},
        "town": {
            "cuts": [{"id": "seam_cut", "kind": "hillside", "rect": list(seam), "floor": 80, "benches": []},
                     {"id": "the_cut", "kind": "traced", "outline": outline, "floor": 70,
                      "bench": {"rise": 3, "run": 4, "levels": 3}}],
            "streets": streets if streets is not None else [{"id": "row", "polyline": [[14, 60], [20, 64]], "width": 3}],
            "houses": houses if houses is not None else [{"id": "hut", "rect": [12, 66, 16, 70]}],
        },
        "mine": {"seam": {"cut": "seam_cut"},
                 "features": [{"id": "adit", "kind": "tube", "path": [[35, 81, 17], [35, 81, 24]], "r": 1, "height": 4}]},
    }


def _problems(spec):
    return RA.pocket_problems(spec, _Grid(), _ground, {})


# A square in the middle of the basin, well clear of its walls, with a gap to the seam yard on the west side.
INSIDE = [[24, 24], [68, 24], [68, 68], [24, 68]]


def test_a_quarry_inside_the_pocket_with_its_inset_is_clean():
    spec = _spec([[24, 24], [67, 24], [67, 67], [24, 67]],
                 streets=[{"id": "row", "polyline": [[14, 60], [18, 40]], "width": 3}],
                 houses=[{"id": "hut", "rect": [12, 30, 16, 34]}])
    spec["town"]["streets"][0]["polyline"] = [[14, 60], [16, 20]]
    assert _problems(spec) == []


# Without it a traced outline can be drawn over the pocket's wall and the quarry cuts into the rim crags.
def test_a_quarry_that_leaves_the_pocket_is_reported():
    spec = _spec([[24, 24], [90, 24], [90, 68], [24, 68]])
    probs = _problems(spec)
    assert any("outside the pocket" in p for p in probs), probs


# Without it a quarry may be drawn right up to the pocket's edge, where its wall is the rim itself.
def test_a_quarry_against_the_pocket_edge_is_reported():
    spec = _spec([[9, 24], [40, 24], [40, 68], [9, 68]])
    probs = _problems(spec)
    assert any("within 4 of the pocket's edge" in p for p in probs), probs


# The causeway between the two cuts exists for this: a quarry across the floor would strand the camp.
def test_a_quarry_that_seals_the_seam_yard_off_is_reported():
    spec = _spec([[7, 30], [72, 30], [72, 50], [7, 50]],
                 streets=[{"id": "row", "polyline": [[14, 60], [16, 55]], "width": 3}],
                 houses=[{"id": "hut", "rect": [12, 64, 16, 68]}],
                 seam=(30, 10, 40, 16))
    probs = _problems(spec)
    assert any("cannot be reached on foot" in p for p in probs), probs


def test_a_street_or_a_house_inside_a_quarry_is_reported():
    spec = _spec([[24, 24], [67, 24], [67, 67], [24, 67]],
                 streets=[{"id": "row", "polyline": [[30, 30], [40, 40]], "width": 3}],
                 houses=[{"id": "hut", "rect": [50, 50, 54, 54]}])
    probs = _problems(spec)
    assert any("street row runs through a quarry" in p for p in probs), probs
    assert any("house hut stands in a quarry" in p for p in probs), probs


# Two implementations of the data's `geometry` words; if they drift the audit stops checking what was built.
@pytest.mark.parametrize("cut", [c for c in SPEC["town"]["cuts"] if c["kind"] in ("traced", "trench")],
                         ids=lambda c: c["id"])
def test_generator_and_audit_rasterise_every_traced_and_trench_footprint_alike(cut):
    a = RM.cut_columns(cut)
    assert a and a == RA.columns_of_cut(cut)


@pytest.mark.parametrize("cut", [c for c in SPEC["town"]["cuts"] if c["kind"] == "traced"], ids=lambda c: c["id"])
def test_every_traced_outline_is_a_simple_ring(cut):
    ring = cut["outline"]
    assert len(ring) >= 4 and len(ring) == len({tuple(p) for p in ring}), "a repeated vertex"
    assert ring[0] != ring[-1], "the ring is closed by the even-odd rule, not by a repeated last vertex"

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def hits(p1, p2, p3, p4):
        d1, d2 = cross(p3, p4, p1), cross(p3, p4, p2)
        d3, d4 = cross(p1, p2, p3), cross(p1, p2, p4)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        for j in range(i + 1, n):
            if j in (i, (i + 1) % n) or (j + 1) % n == i:
                continue
            c, d = ring[j], ring[(j + 1) % n]
            assert not hits(a, b, c, d), "edges %d and %d of %s cross" % (i, j, cut["id"])


# Without it the reshape's own claim (how much of the pocket the workings take) is a sentence nobody measures.
def test_the_data_records_how_the_pocket_is_measured():
    pk = SPEC["pocket"]
    assert pk["seed"] and pk["floor_y"] and pk["inset"] >= 1
    assert pk["measured"]["columns"] > 0
    assert "heightmap" in pk["why"] and "never from a world" in pk["why"]
