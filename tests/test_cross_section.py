"""cross_section.py and landmarks.py against surfaces with known answers.

Profiles are built analytically so floor width, depth, wall angle and shape
are known exactly; the CLI is exercised on the fixture trench, whose V
cross-section is defined in tools/make_fixture.py.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import cross_section as X   # noqa: E402
import landmarks as LM      # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "terrain"
W = ["--world", str(FIXTURE / "world.json")]
OFF = np.arange(-100.0, 100.0 + 1e-9, 1.0)


def prof_v(depth=30.0, half=30.0, top=100.0):
    return np.where(np.abs(OFF) <= half, top - depth + depth * np.abs(OFF) / half, top)


def analyse(prof, **kw):
    kw.setdefault("thalweg_window", None)
    return X.analyse_profile(OFF, prof, X.params(**kw))


# ------------------------------------------------------------ profile shapes


def test_v_valley_measures_exactly():
    r = analyse(prof_v())
    assert r["shape"] == "V"
    assert r["floor_y"] == pytest.approx(70.0)
    assert r["depth"] == pytest.approx(30.0)
    assert r["wall_left_deg"] == pytest.approx(45.0, abs=0.5)
    assert r["wall_right_deg"] == pytest.approx(45.0, abs=0.5)
    assert r["b_mean"] == pytest.approx(1.0, abs=0.05)
    # rims are the shoulders at +-30, not the far ends of the flat transect
    assert r["rim_left"]["offset"] == pytest.approx(-30.0)
    assert r["rim_right"]["offset"] == pytest.approx(30.0)
    # rim to rim: every sample strictly below y100 is |s| < 30, so 59 samples
    assert r["top_width"] == pytest.approx(59.0)


def test_parabolic_valley_is_u():
    prof = np.where(np.abs(OFF) <= 40, 60.0 + 40.0 * (OFF / 40.0) ** 2, 100.0)
    r = analyse(prof)
    assert r["shape"] == "U"
    assert r["b_mean"] == pytest.approx(2.0, abs=0.1)
    assert r["depth"] == pytest.approx(40.0)


def test_wide_floor_is_flat_floored():
    # floor y70 over |s|<=30, then 45 degree walls to y100 at |s|=60
    prof = np.clip(70.0 + np.maximum(np.abs(OFF) - 30.0, 0.0), None, 100.0)
    r = analyse(prof)
    assert r["shape"] == "flat_floored"
    # tolerance is max(2, 0.1*30)=3 blocks: |s| <= 33 is on the floor
    assert r["floor_width"] == pytest.approx(67.0)
    assert r["wall_left_deg"] == pytest.approx(45.0, abs=0.5)
    assert r["depth"] == pytest.approx(30.0)


def test_unequal_walls_are_asymmetric():
    # left wall 45 degrees over 30 blocks, right wall rises 30 over 150: 11.3 degrees
    prof = np.where(OFF < 0, np.minimum(70.0 - OFF, 100.0), np.minimum(70.0 + OFF * 0.2, 100.0))
    r = analyse(prof)
    assert r["asymmetric"] is True
    assert r["shape"] == "asymmetric"
    assert r["wall_left_deg"] == pytest.approx(45.0, abs=0.5)
    assert r["wall_right_deg"] == pytest.approx(11.3, abs=0.5)


def test_flat_ground_has_no_valley():
    r = analyse(np.full(OFF.shape, 100.0))
    assert r["shape"] == "none"
    assert r["depth"] == pytest.approx(0.0)


def test_a_hill_beyond_the_shoulder_is_not_the_rim():
    # V valley rimmed at y100, then a dip to 90 and a hill to 140 further out
    prof = prof_v()
    prof = np.where((OFF > 45) & (OFF < 60), 90.0, prof)
    prof = np.where(OFF >= 60, 140.0, prof)
    r = analyse(prof)
    assert r["rim_right"]["y"] == pytest.approx(100.0)
    assert r["depth"] == pytest.approx(30.0)


def test_gently_rising_country_beyond_the_wall_is_not_wall():
    # a 45 degree V to y100 at +-30, then ground rising at 1.4 degrees to the ends
    prof = np.where(np.abs(OFF) <= 30, prof_v(), 100.0 + (np.abs(OFF) - 30.0) / 40.0)
    r = analyse(prof)
    assert r["rim_left"]["offset"] == pytest.approx(-30.0, abs=1.0)
    assert r["rim_right"]["offset"] == pytest.approx(30.0, abs=1.0)
    assert r["depth"] == pytest.approx(30.0, abs=0.1)
    # with the slope-break rule off, the walk runs on to the end of the transect
    r_off = analyse(prof, rim_flat_deg=None)
    # (it advances in rim_eps steps, so it stops within a few blocks of the end)
    assert r_off["rim_right"]["offset"] > 90.0


def test_a_bench_partway_up_the_wall_does_not_end_it():
    # 45 degree walls from y70, a 60-block bench at y80, then 45 degrees on to y100
    a = np.abs(OFF)
    prof = np.select([a <= 10, a <= 70, a <= 90], [70.0 + a, 80.0, 80.0 + (a - 70.0)], 100.0)
    r = analyse(prof)
    assert r["rim_right"]["y"] == pytest.approx(100.0)
    assert r["depth"] == pytest.approx(30.0)


def test_level_width_reports_the_run_below_a_y():
    # below y85 the V is |s| < 15: 29 samples
    r = analyse(prof_v(), level=85.0)
    assert r["level_width"] == pytest.approx(29.0)


def test_thalweg_window_ignores_deeper_ground_at_the_edges():
    prof = prof_v()
    prof[:5] = 10.0      # sea at the far left end of the transect
    r = analyse(prof, thalweg_window=100.0)
    assert r["floor_y"] == pytest.approx(70.0)


# ------------------------------------------------------------ geometry


def test_stations_follow_each_segment():
    sts, total = X.stations([(0, 0), (100, 0), (100, 50)], 50)
    assert total == pytest.approx(150.0)
    assert [round(d) for d, _, _ in sts] == [0, 50, 100, 150]
    assert tuple(sts[1][2]) == (1.0, 0.0)
    assert tuple(sts[3][2]) == (0.0, 1.0)


def test_bilinear_is_exact_on_a_plane():
    z, x = np.mgrid[0:10, 0:10].astype(float)
    h = 3.0 * x + 2.0 * z + 1.0
    assert X.bilinear(h, 4.25, 6.5) == pytest.approx(3 * 4.25 + 2 * 6.5 + 1)


# ------------------------------------------------------------ CLI on the fixture


def test_fixture_trench_is_a_45_degree_v(tmp_path):
    """The trench is floor y85 at z=200 with walls of exactly 1 up to y100.

    x stays below 72, where the ridge band begins; a transect at x=90 reaches
    the ridge flank at z=170 and is correctly reported as asymmetric."""
    out = tmp_path / "trench.json"
    assert X.main(W + ["--polyline", "20,200;60,200", "--width", "60",
                       "--spacing", "20", "--sample-step", "1", "--out", str(out)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    s = d["summary"]
    assert s["stations"] == 3
    assert s["shape_counts"]["V"] == 3
    assert s["floor_y"] == [85.0, 85.0]
    assert s["depth"]["median"] == pytest.approx(15.0, abs=0.05)
    assert s["wall_deg"]["median"] == pytest.approx(45.0, abs=0.5)
    assert d["source"]["heightmap_sha256"]


def test_cli_reads_the_axis_from_a_landmark(tmp_path):
    lm = {"schema": "cobblers.landmarks/1", "landmarks": [{
        "id": "trench", "kind": "valley", "status": "built",
        "axes": [{"id": "floor", "polyline": [[20, 200], [90, 200]], "section_width": 60}],
    }]}
    lpath = tmp_path / "landmarks.json"
    lpath.write_text(json.dumps(lm), encoding="utf-8")
    out = tmp_path / "s.json"
    assert X.main(W + ["--landmark", "trench", "--landmarks", str(lpath),
                       "--sample-step", "1", "--out", str(out)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["landmark"] == "trench" and d["axis"] == "floor"
    assert d["summary"]["dominant_shape"] == "V"


def test_cli_refuses_the_real_unconfigured_terrain(tmp_path, monkeypatch):
    monkeypatch.delenv("COBBLERS_SOURCE_ROOT", raising=False)
    with pytest.raises(SystemExit) as exc:
        X.main(["--polyline", "0,0;10,0", "--width", "10", "--out", str(tmp_path / "n.json")])
    assert "terrain unavailable" in str(exc.value)


# ------------------------------------------------------------ landmarks


def _doc(**over):
    lm = {"id": "rift", "kind": "rift", "status": "built", "water": "never",
          "anchor": {"x": 10, "z": 20}, "anchors": {"rim_n": {"x": 1, "z": 2}},
          "extent": {"polygons": [[[10, 10], [29, 10], [29, 29], [10, 29]]]}}
    lm.update(over)
    return {"schema": "cobblers.landmarks/1", "landmarks": [lm]}


def test_landmark_points_resolve():
    doc = _doc()
    assert LM.point(doc, "rift") == (10, 20)
    assert LM.point(doc, "rift.rim_n") == (1, 2)
    with pytest.raises(LM.LandmarkError):
        LM.point(doc, "rift.nope")


@pytest.mark.parametrize("over,needle", [
    ({"status": "done"}, "status"),
    ({"water": "sometimes"}, "water"),
    ({"extent": {"polygons": [[[0, 0], [1, 1]]]}}, "fewer than 3"),
])
def test_landmark_check_rejects(over, needle):
    assert any(needle in p for p in LM.check(_doc(**over)))


def test_no_water_mask_covers_the_polygon():
    m = LM.no_water_mask(_doc(), (40, 40))
    assert m[15, 15] and m[10, 10] and m[29, 29]
    assert not m[5, 5] and not m[35, 35]
    assert not LM.no_water_mask(_doc(water="allowed"), (40, 40)).any()
