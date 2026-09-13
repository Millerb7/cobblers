"""Tools that query data/landmarks.json instead of inferring features.

Everything runs on the synthetic fixture with a temporary landmarks file, so the
expected answers follow from tools/make_fixture.py geometry:

  ridge  crest x=112 over z 90..170, apex y140, flanks exactly 1
  sea    z 235..255 at y40, below sea level 62, touching the map edge
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import cell_stats as C      # noqa: E402
import landforms as LF      # noqa: E402
import sightlines as S      # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "terrain"
W = ["--world", str(FIXTURE / "world.json")]


def write_landmarks(tmp_path, landmarks):
    p = tmp_path / "landmarks.json"
    p.write_text(json.dumps({"schema": "cobblers.landmarks/1", "landmarks": landmarks}),
                 encoding="utf-8")
    return p


RIDGE = {"id": "ridge", "kind": "mountain", "name": "Ridge", "status": "built",
         "anchor": {"x": 112, "z": 130}, "anchors": {"west_foot": {"x": 60, "z": 130}},
         "extent": {"polygons": [[[80, 100], [144, 100], [144, 160], [80, 160]]]}}
FAR_BASE = {"id": "far_base", "kind": "pass", "name": "Behind the ridge", "status": "planned",
            "anchor": {"x": 180, "z": 130},
            "extent": {"polygons": [[[172, 122], [200, 122], [200, 138], [172, 138]]]}}
# the west third of the sea band, declared never-water like the rift
VOID = {"id": "void", "kind": "rift", "name": "Void strip", "status": "built", "water": "never",
        "anchor": {"x": 30, "z": 245},
        "extent": {"polygons": [[[0, 232], [63, 232], [63, 255], [0, 255]]]}}


# ----------------------------------------------------------------- sightlines


def test_anchor_references_resolve_to_coordinates(tmp_path):
    lp = write_landmarks(tmp_path, [RIDGE])
    out = tmp_path / "s.json"
    assert S.main(W + ["--landmarks", str(lp), "--from", "@ridge.west_foot", "--eye", "2",
                       "--target", "@ridge", "--out", str(out)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["parameters"]["from"] == [60, 130]
    r = d["results"][0]
    assert r["target"] == {"x": 112, "z": 130, "landmark": "ridge"}
    assert r["visible"] is True


def test_extent_target_is_visible_when_any_part_is(tmp_path):
    """From the west foot the ridge's near flank and crest are in view."""
    lp = write_landmarks(tmp_path, [RIDGE])
    out = tmp_path / "s.json"
    S.main(W + ["--landmarks", str(lp), "--from", "60,130", "--eye", "2",
                "--target", "@ridge*", "--out", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))["results"][0]
    assert r["visible"] is True
    assert 0 < r["visible_samples"] < r["samples"]


def test_extent_hidden_behind_the_ridge_is_blocked(tmp_path):
    """Flat ground east of a y140 crest cannot be seen from y102 on the west."""
    lp = write_landmarks(tmp_path, [FAR_BASE])
    out = tmp_path / "s.json"
    S.main(W + ["--landmarks", str(lp), "--from", "60,130", "--eye", "2",
                "--target", "@far_base*", "--out", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))["results"][0]
    assert r["visible"] is False
    assert r["visible_samples"] == 0


def test_plan_runs_several_sets_on_one_load(tmp_path):
    lp = write_landmarks(tmp_path, [RIDGE, FAR_BASE])
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"sets": [
        {"id": "west", "from": "@ridge.west_foot", "eye": 2, "targets": ["@ridge*", "@far_base"]},
        {"id": "crest", "from": "112,130", "eye": 2, "targets": ["@far_base*"]},
    ]}), encoding="utf-8")
    out = tmp_path / "plan_out.json"
    assert S.main(W + ["--landmarks", str(lp), "--plan", str(plan), "--out", str(out)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    sets = {s["id"]: s for s in d["sets"]}
    assert [r["visible"] for r in sets["west"]["results"]] == [True, False]
    assert sets["crest"]["results"][0]["visible"] is True


def test_unknown_landmark_is_refused_before_terrain_loads(tmp_path):
    lp = write_landmarks(tmp_path, [RIDGE])
    with pytest.raises(SystemExit, match="landmarks: no landmark"):
        S.main(["--landmarks", str(lp), "--from", "@nope", "--target", "t:1,1",
                "--out", str(tmp_path / "x.json")])


def test_vectorised_cast_matches_the_fixture_blocker():
    """Same blocker as the scalar version: the near flank at x=74, ground y102."""
    import terrain as T
    h, _ = T.load(FIXTURE / "world.json")
    r = S.cast(h, (60, 130), 2.0, {"x": 170, "z": 130}, 0.0)
    assert r["visible"] is False
    assert r["blocked_at"]["x"] == pytest.approx(74.0, abs=1.0)
    assert r["blocked_at"]["ground_y"] == pytest.approx(102.0, abs=0.2)


# ------------------------------------------------------- never-water landmarks


def test_landforms_class_void_floor_not_water(tmp_path):
    lp = write_landmarks(tmp_path, [VOID])
    outdir = tmp_path / "lf"
    assert LF.main(W + ["--landmarks", str(lp), "--out", str(outdir)]) == 0
    d = json.loads((outdir / "landforms.json").read_text(encoding="utf-8"))
    cls = np.load(outdir / "classes.npy")
    ids = d["class_ids"]
    # at 8-block resolution the sea band covers rows 29..31; the void polygon
    # covers columns 0..7 of those rows
    assert (cls[29:32, 0:8] == ids["void_floor"]).all()
    assert (cls[29:32, 8:] == ids["sea"]).all()
    assert d["void_fraction"] == pytest.approx(24 / 1024, abs=1e-4)
    assert d["inland_water_bodies"] == []


def test_landforms_without_landmarks_reads_it_as_sea(tmp_path):
    outdir = tmp_path / "lf"
    assert LF.main(W + ["--no-landmarks", "--out", str(outdir)]) == 0
    d = json.loads((outdir / "landforms.json").read_text(encoding="utf-8"))
    assert d["void_fraction"] == 0.0
    assert d["landmarks"] is None


def test_cell_stats_counts_void_separately(tmp_path):
    lp = write_landmarks(tmp_path, [VOID])
    out = tmp_path / "cells.json"
    assert C.main(W + ["--landmarks", str(lp), "--coast-factor", "1", "--out", str(out)]) == 0
    cells = {c["id"]: c for c in json.loads(out.read_text(encoding="utf-8"))["cells"]}
    t = cells["D1"]["terrain"]
    # D1 is x 0..63, z 192..255: 21 of 64 rows are below sea level, all inside the void polygon
    assert t["void_fraction"] == pytest.approx(21 / 64, abs=1e-4)
    assert t["water_fraction"] == pytest.approx(0.0, abs=1e-4)
    assert cells["D2"]["terrain"]["water_fraction"] == pytest.approx(21 / 64, abs=1e-4)


def test_malformed_landmarks_stop_the_tool(tmp_path):
    lp = write_landmarks(tmp_path, [dict(VOID, water="sometimes")])
    with pytest.raises(SystemExit, match="landmarks"):
        C.main(W + ["--landmarks", str(lp), "--out", str(tmp_path / "c.json")])
