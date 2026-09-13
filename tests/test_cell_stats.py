"""cell_stats against the synthetic fixture, with hand-computed answers.

The fixture is a 4x4 grid of 64-block cells. Sea fills z 235..255, so every
cell in row D (z 192..255) has 21 of 64 rows under water.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import terrain as T      # noqa: E402
import cell_stats as C   # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "terrain"


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("cells") / "cells.json"
    assert C.main(["--world", str(FIXTURE / "world.json"),
                   "--coast-factor", "1", "--out", str(out)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    return d, {c["id"]: c for c in d["cells"]}


def test_every_cell_is_measured(result):
    d, cells = result
    assert len(cells) == 16
    assert set(cells) == {r + c for r in "ABCD" for c in "1234"}


def test_cell_bounds_follow_the_grid(result):
    _, cells = result
    assert cells["A1"]["bounds"] == {"min_x": 0, "min_z": 0, "max_x": 63, "max_z": 63}
    assert cells["D4"]["bounds"] == {"min_x": 192, "min_z": 192, "max_x": 255, "max_z": 255}


def test_plateau_cell_elevation(result):
    """A1 holds base ground at 100 and part of the 120 plateau."""
    _, cells = result
    t = cells["A1"]["terrain"]
    assert t["min_y"] == pytest.approx(100.0, abs=0.01)
    assert t["max_y"] == pytest.approx(120.0, abs=0.01)
    assert t["land_fraction"] == 1.0


def test_sea_row_land_fraction(result):
    """21 of 64 rows in row D are sea, so land is exactly 43/64."""
    _, cells = result
    for col in "1234":
        t = cells["D" + col]["terrain"]
        assert t["land_fraction"] == pytest.approx(43 / 64, abs=1e-4)
        assert t["water_fraction"] == pytest.approx(21 / 64, abs=1e-4)


def test_sea_is_classified_as_sea_not_lake(result):
    """The sea band touches the map edge, so none of it is inland water."""
    d, cells = result
    assert all(c["coast"]["inland_water_fraction"] == 0.0 for c in cells.values())
    assert d["totals"]["inland_water_fraction"] == 0.0


def test_distance_to_sea_is_exact_on_the_axis(result):
    """Row A (z 0..63) is 172 to 235 blocks from sea, straight down the z axis."""
    _, cells = result
    coast = cells["A2"]["coast"]
    assert coast["min_distance_to_sea"] == pytest.approx(172.0, abs=1.0)
    assert coast["max_distance_to_sea"] == pytest.approx(235.0, abs=1.0)


def test_row_d_land_touches_the_sea(result):
    _, cells = result
    assert cells["D3"]["coast"]["min_distance_to_sea"] == pytest.approx(1.0, abs=0.01)


def test_carries_heightmap_provenance(result):
    d, cells = result
    sha = T.load_world(FIXTURE / "world.json")["heightmap"]["sha256"]
    assert d["source"]["heightmap_sha256"] == sha
    assert all(c["terrain"]["computed_from_sha256"] == sha for c in cells.values())


def test_enclosed_water_is_inland():
    """A lake with no path to the border must not count as sea."""
    water = np.zeros((20, 20), dtype=bool)
    water[0, :] = True            # sea along the top edge
    water[8:12, 8:12] = True      # enclosed lake
    sea = C.connected_to_edge(water)
    assert sea[0].all()
    assert not sea[8:12, 8:12].any()


def test_diagonal_pinch_does_not_leak():
    """4-connectivity: water touching only at a corner is not one body."""
    water = np.zeros((10, 10), dtype=bool)
    water[0, 0] = True
    water[1, 1] = True
    sea = C.connected_to_edge(water)
    assert sea[0, 0] and not sea[1, 1]


def test_refuses_an_unset_origin(tmp_path):
    cfg = json.loads((FIXTURE / "world.json").read_text(encoding="utf-8"))
    cfg["grid"]["origin_x"] = None
    cfg["source_root"] = str(FIXTURE)
    w = tmp_path / "world.json"
    w.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(SystemExit, match="origin is unset"):
        C.main(["--world", str(w), "--out", str(tmp_path / "x.json")])
