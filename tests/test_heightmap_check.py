"""tools/heightmap_check.py check(): a heightmap file is refused when it shows the signs of silent corruption.

Every case writes a synthetic 256x256 16-bit PNG to tmp_path and checks it with a small world dict whose
heightmap.width is 256 and whose import line is the real one. Each corruption is applied to an otherwise clean file,
so a failure can only come from the check that names it.

Not covered: a tile shifted by a few rows on smooth terrain makes no jumps over 24 blocks and is not caught by the
tears check (on the real heightmap a 1024-block tile shifted 64 rows made 0 tears); only the allowed-box comparison
with a predecessor catches it (tested below). Byte-order and 16-bit decoding on other PNG encoders are not covered.
"""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import heightmap_check as H  # noqa: E402
import sculpt as S  # noqa: E402

N = 256
IMPORT = {"input_units": "fraction_of_full_scale", "low_in": 0.0, "high_in": 0.996078431, "low_out": 10.093458,
          "high_out": 200, "water_level": 62, "clamp_low": True, "clamp_high": True}
WORLD = {"heightmap": {"width": N, "bit_depth": 16}, "vertical": {"sea_level": 62}, "import": IMPORT}


def _clean_raw():
    zz, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    y = 70 + 40 * np.sin(xx / 30) * np.cos(zz / 40) + 20 * np.sin((xx + zz) / 17)     # land and sea, no cliffs
    return S.y_to_raw(y, WORLD).astype(np.uint16)


def _save(tmp_path, raw, name):
    p = tmp_path / name
    Image.fromarray(np.asarray(raw).astype(np.uint16)).save(p)
    return p


@pytest.fixture
def clean(tmp_path):
    raw = _clean_raw()
    return raw, _save(tmp_path, raw, "clean.png")


# removing this lets the baseline for every corruption case below fail on its own, so each case proves nothing
def test_clean_file_passes_with_and_without_predecessor(clean):
    raw, path = clean
    rep = H.check(path, WORLD, sha=hashlib.sha256(path.read_bytes()).hexdigest())
    assert rep["ok"] and rep["failures"] == [], rep["failures"]
    assert rep["tears"] == 0 and rep["rail_share"] == 0 and rep["multiple_of_257_share"] < 0.01
    rep = H.check(path, WORLD, predecessor=path, allow=[(0, 0, 10, 10)])
    assert rep["ok"] and rep["predecessor"]["columns_changed"] == 0


# removing this lets an 8-bit heightmap scaled up to 16 bits (every value a multiple of 257, one block per 1/255 of
# the range) be imported as if it had full precision
def test_eight_bit_data_scaled_by_257_fails(clean, tmp_path):
    raw, _ = clean
    eight = (raw.astype(np.int32) // 257).clip(0, 255) * 257
    rep = H.check(_save(tmp_path, eight, "eight.png"), WORLD)
    assert not rep["ok"] and any("multiples of 257" in f for f in rep["failures"]), rep["failures"]


# removing this lets a clipped or mis-scaled file with values piled on 0 or 65535 through
@pytest.mark.parametrize("rail", [0, 65535])
def test_values_piled_on_a_rail_fail(clean, tmp_path, rail):
    raw, _ = clean
    bad = raw.copy()
    bad[:4, :] = rail                                           # 4 of 256 rows: 1.6% of columns
    rep = H.check(_save(tmp_path, bad, "rail.png"), WORLD)
    assert any("sit on a rail" in f for f in rep["failures"]), rep["failures"]
    ok = raw.copy()
    ok[0, :64] = rail                                           # 0.1%: under the 0.5% allowance
    assert not any("rail" in f for f in H.check(_save(tmp_path, ok, "rail_ok.png"), WORLD)["failures"])


# removing this lets a torn tile (here byte-swapped, as a bad writer would leave it) be imported: it shows as
# thousands of new jumps over 24 blocks against the predecessor
def test_torn_tile_fails_against_its_predecessor(clean, tmp_path):
    raw, path = clean
    torn = raw.copy()
    t = torn[64:192, 64:192]
    torn[64:192, 64:192] = (t >> 8) | ((t & 0xFF) << 8)
    rep = H.check(_save(tmp_path, torn, "torn.png"), WORLD, predecessor=path)
    assert rep["tears"] > 1000
    assert any("tears" in f for f in rep["failures"]), rep["failures"]


# removing this lets a run of duplicated land rows or columns (a stuck writer repeating a scanline) through
@pytest.mark.parametrize("axis", ["rows", "columns"])
def test_duplicated_land_rows_fail(clean, tmp_path, axis):
    raw, path = clean
    bad = raw.copy()
    if axis == "rows":
        bad[100:110, :] = bad[100, :]                           # 10 identical consecutive rows
    else:
        bad[:, 100:110] = bad[:, 100:101]
    rep = H.check(_save(tmp_path, bad, "dup.png"), WORLD, predecessor=path)
    key = "duplicate_row_run" if axis == "rows" else "duplicate_col_run"
    assert rep[key] == 10
    assert any(key in f for f in rep["failures"]), rep["failures"]
    short = raw.copy()
    if axis == "rows":
        short[100:106, :] = short[100, :]                       # 6: under the run of 8
    else:
        short[:, 100:106] = short[:, 100:101]
    assert not any(key in f for f in H.check(_save(tmp_path, short, "dup_ok.png"), WORLD, predecessor=path)["failures"])


# removing this lets a file that is not the recorded one pass under the recorded name
def test_sha_mismatch_fails(clean):
    raw, path = clean
    rep = H.check(path, WORLD, sha="0" * 64)
    assert any("is not the expected" in f for f in rep["failures"]), rep["failures"]


# removing this lets an edit (or a shifted tile on smooth ground, which makes no tears) change columns outside the
# boxes where changes were expected
def test_changes_outside_allowed_boxes_fail(clean, tmp_path):
    raw, path = clean
    edited = raw.copy()
    edited[20:30, 20:30] += 50                                  # inside the allowed box
    edited[200:210, 150:160] += 50                              # outside it
    p = _save(tmp_path, edited, "edited.png")
    rep = H.check(p, WORLD, predecessor=path, allow=[(0, 0, 60, 60)])
    assert rep["predecessor"]["changed_outside_allowed"] == 100
    assert any("outside the allowed boxes" in f for f in rep["failures"]), rep["failures"]
    assert H.check(p, WORLD, predecessor=path, allow=[(0, 0, 60, 60), (150, 200, 159, 209)])["ok"]
    shifted = raw.copy()
    shifted[0:128, 128:256] = np.roll(raw[0:128, 128:256], 6, axis=0)
    rep = H.check(_save(tmp_path, shifted, "shifted.png"), WORLD, predecessor=path, allow=[(0, 0, 60, 60)])
    assert any("outside the allowed boxes" in f for f in rep["failures"])


# removing this lets an 8-bit or wrongly sized PNG be decoded and checked as if it were the heightmap
def test_wrong_depth_or_size_is_refused(clean, tmp_path):
    raw, _ = clean
    p8 = tmp_path / "eight_bit.png"
    Image.fromarray((raw // 257).astype(np.uint8)).save(p8)
    with pytest.raises(ValueError, match="not 16-bit"):
        H.check(p8, WORLD)
    small = _save(tmp_path, raw[:128, :128], "small.png")
    with pytest.raises(ValueError, match="not 256x256"):
        H.check(small, WORLD)
