"""structure_candidates.py: java.util.Random parity and random-spread candidate geometry."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import structure_candidates as SC  # noqa: E402


def test_java_random_matches_known_values():
    # Well-known java.util.Random outputs
    assert SC.JavaRandom(0).next_int() == -1155484576
    assert SC.JavaRandom(42).next_int() == -1170105035
    assert abs(SC.JavaRandom(0).next_float() - 0.73096776) < 1e-7


def test_next_int_bound_is_in_range_and_power_of_two_path():
    r = SC.JavaRandom(123)
    vals = [r.next_int(10) for _ in range(500)]
    assert min(vals) >= 0 and max(vals) <= 9 and len(set(vals)) == 10
    r2 = SC.JavaRandom(123)
    assert all(0 <= r2.next_int(16) < 16 for _ in range(100))


def test_candidate_stays_in_its_cell_window():
    for spread in ("linear", "triangular"):
        for gx, gz in ((0, 0), (-3, 5), (7, -2)):
            cx, cz = SC.candidate_chunk(987654321, gx, gz, 40, 20, 14357620, spread)
            assert gx * 40 <= cx < gx * 40 + 20
            assert gz * 40 <= cz < gz * 40 + 20


def test_candidates_are_deterministic_and_bounded():
    pl = {"spacing": 32, "separation": 8, "salt": 10387312}
    b = {"min_x": -2048, "min_z": -2048, "max_x": 2047, "max_z": 2047}
    a, _, _ = SC.candidates(42, pl, b)
    again, _, _ = SC.candidates(42, pl, b)
    assert a == again
    assert all(-128 <= c["chunk"][0] <= 127 and -128 <= c["chunk"][1] <= 127 for c in a)
    assert 49 <= len(a) <= 64  # 8x8 cells overlap the box; most windows fall inside


def test_frequency_filter_removes_some_candidates():
    pl = {"spacing": 4, "separation": 1, "salt": 1, "frequency": 0.25}
    b = {"min_x": 0, "min_z": 0, "max_x": 1599, "max_z": 1599}
    kept, removed, unmodelled = SC.candidates(7, pl, b)
    assert not unmodelled
    share = len(kept) / (len(kept) + removed)
    assert 0.15 < share < 0.35
