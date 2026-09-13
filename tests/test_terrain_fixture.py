"""The synthetic fixture must have exactly the properties the tool tests assume.

If these fail, every expectation in test_analysis_tools.py is meaningless.
Values here are hand-computed from the feature definitions in
tools/make_fixture.py, not read back from a golden file.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import terrain as T  # noqa: E402
import make_fixture as F  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "terrain"


@pytest.fixture(scope="module")
def heights():
    h, _ = T.load(FIXTURE / "world.json")
    return h


@pytest.fixture(scope="module")
def world():
    return T.load_world(FIXTURE / "world.json")


def test_fixture_is_deterministic(tmp_path):
    """Regenerating the fixture must reproduce it byte for byte."""
    F.main(["--out", str(tmp_path)])
    for name in ("land_fixture.png", "world.json"):
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == \
            hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest(), name


def test_fixture_config_is_portable():
    """A committed config must not pin a machine-specific absolute path."""
    import json
    cfg = json.loads((FIXTURE / "world.json").read_text(encoding="utf-8"))
    assert not Path(cfg["source_root"]).is_absolute()


def test_recorded_hash_matches_file(world):
    """The fixture world.json pins its own heightmap, like the real one must."""
    digest = hashlib.sha256((FIXTURE / "land_fixture.png").read_bytes()).hexdigest()
    assert world["heightmap"]["sha256"] == digest


def test_shape_and_range(heights):
    assert heights.shape == (256, 256)
    assert heights.min() == pytest.approx(40.0, abs=0.01)   # sea floor
    assert heights.max() == pytest.approx(140.0, abs=0.01)  # cone apex / ridge crest


@pytest.mark.parametrize("x,z,expected,what", [
    (20, 80, 100.0, "flat base"),
    (30, 30, 120.0, "plateau interior"),
    (192, 64, 140.0, "cone apex"),
    (212, 64, 120.0, "cone flank 20 blocks out"),
    (112, 130, 140.0, "ridge crest"),
    (100, 130, 128.0, "ridge west flank, 12 blocks out"),
    (124, 130, 128.0, "ridge east flank, 12 blocks out"),
    (100, 200, 85.0, "trench floor"),
    (100, 208, 93.0, "trench wall, 8 blocks from the floor"),
    (100, 240, 40.0, "sea floor"),
])
def test_known_heights(heights, x, z, expected, what):
    assert heights[z, x] == pytest.approx(expected, abs=0.01), what


@pytest.mark.parametrize("x,z,expected,what", [
    (20, 80, 0.0, "flat base is flat"),
    (30, 30, 0.0, "plateau interior is flat"),
    (212, 64, 1.0, "cone flank rises one block per block"),
    (100, 130, 1.0, "ridge west flank rises one block per block"),
    (124, 130, 1.0, "ridge east flank rises one block per block"),
    (100, 208, 1.0, "trench wall rises one block per block"),
])
def test_known_slopes(heights, x, z, expected, what):
    assert T.slope(heights)[z, x] == pytest.approx(expected, abs=0.01), what


def test_slope_degrees_on_a_unit_flank(heights):
    """A 1.0 rise over run is 45 degrees, exactly."""
    assert T.slope_degrees(heights)[130, 100] == pytest.approx(45.0, abs=0.5)


@pytest.mark.parametrize("x,z,expected,what", [
    (100, 130, 270.0, "ridge west flank drains west"),
    (124, 130, 90.0, "ridge east flank drains east"),
    (100, 208, 0.0, "trench south wall drains north toward the floor"),
    (100, 192, 180.0, "trench north wall drains south toward the floor"),
])
def test_known_aspects(heights, x, z, expected, what):
    asp = T.aspect_degrees(heights)[z, x]
    diff = abs((asp - expected + 180) % 360 - 180)
    assert diff < 1.0, "%s: got %.1f, expected %.1f" % (what, asp, expected)


def test_flat_ground_has_no_aspect(heights):
    assert np.isnan(T.aspect_degrees(heights)[80, 20])


def test_land_fraction(heights, world):
    """21 of 256 rows are sea, so land is exactly 235/256."""
    land = (heights > T.sea_level(world)).mean()
    assert land == pytest.approx(235.0 / 256.0, abs=1e-6)


def test_import_mapping_is_exactly_invertible():
    """65535 = 255 * 257, so the fixture's samples round-trip without loss."""
    world = T.load_world(FIXTURE / "world.json")
    samples = np.array([[0, 257, 257 * 100, 65535]], dtype=np.uint16)
    y = T.sample_to_height(samples, world)
    assert list(y[0]) == pytest.approx([0.0, 1.0, 100.0, 255.0], abs=1e-9)
