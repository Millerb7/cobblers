"""Each analysis tool against the synthetic fixture, with hand-computed answers.

Every expectation here is derived from the feature geometry in
tools/make_fixture.py, not from a previous run of the tool.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import terrain as T          # noqa: E402
import find_sites            # noqa: E402
import route_path            # noqa: E402
import sightlines            # noqa: E402
import slope_masks           # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "terrain"
W = ["--world", str(FIXTURE / "world.json")]


def run(mod, args, out):
    assert mod.main(args + ["--out", str(out)]) == 0
    return out


def load(out):
    return json.loads(Path(out).read_text(encoding="utf-8"))


# --------------------------------------------------------------- find_sites


def _reference_largest_squares(mask):
    """The textbook O(n) recurrence, written plainly as the oracle."""
    dp = np.zeros(mask.shape, np.int32)
    m = mask.astype(np.int32)
    dp[0, :] = m[0, :]
    dp[:, 0] = m[:, 0]
    for z in range(1, mask.shape[0]):
        for x in range(1, mask.shape[1]):
            if m[z, x]:
                dp[z, x] = 1 + min(dp[z - 1, x], dp[z, x - 1], dp[z - 1, x - 1])
    return dp


@pytest.mark.parametrize("h,w,p,seed", [
    (40, 40, 0.90, 1), (64, 31, 0.70, 2), (50, 77, 0.97, 3),
    (120, 120, 0.85, 4), (1, 30, 0.9, 5), (30, 1, 0.9, 6),
])
def test_vectorised_squares_match_the_reference(h, w, p, seed):
    """The fast recurrence must equal the textbook one cell for cell,
    including the top row and left column where the edge case lives."""
    mask = np.random.default_rng(seed).random((h, w)) < p
    assert np.array_equal(find_sites.largest_squares(mask),
                          _reference_largest_squares(mask))


def test_greedy_extraction_recompute_is_exact():
    """Recomputing only from the taken row must equal a full recompute."""
    mask = np.random.default_rng(9).random((90, 90)) < 0.93
    work = mask.copy()
    dp = find_sites.largest_squares(work)
    z0, z1, x0, x1 = 20, 35, 10, 30
    work[z0:z1 + 1, x0:x1 + 1] = False
    partial = find_sites.largest_squares(work, start_row=z0, dp=dp.copy())
    assert np.array_equal(partial, find_sites.largest_squares(work))


def test_finds_the_plateau_exactly(tmp_path):
    """The plateau is 32x32 at y=120 with zero slope. Nothing else qualifies."""
    out = run(find_sites, W + ["--min-size", "8", "--max-slope", "1",
                               "--bbox", "16,16,47,47", "--top", "5"],
              tmp_path / "sites.json")
    d = load(out)
    assert d["site_count"] == 1
    site = d["sites"][0]
    assert site["size"] == 32
    assert site["height"]["min"] == pytest.approx(120.0, abs=0.01)
    assert site["height"]["max"] == pytest.approx(120.0, abs=0.01)
    assert site["slope_degrees"]["max"] == pytest.approx(0.0, abs=0.01)
    assert d["buildable_fraction"] == pytest.approx(1.0)


def test_max_y_excludes_high_flat_ground(tmp_path):
    """The 120 plateau is flat but above a y110 ceiling, so it must vanish."""
    out = run(find_sites, W + ["--min-size", "8", "--max-slope", "1",
                               "--bbox", "16,16,47,47", "--max-y", "110"],
              tmp_path / "sites.json")
    d = load(out)
    assert d["site_count"] == 0
    assert d["buildable_fraction"] == pytest.approx(0.0)


def test_no_site_is_steeper_than_asked(tmp_path):
    out = run(find_sites, W + ["--min-size", "12", "--max-slope", "3", "--top", "25"],
              tmp_path / "sites.json")
    d = load(out)
    assert d["sites"], "expected at least one flat site on a mostly flat fixture"
    for s in d["sites"]:
        assert s["slope_degrees"]["max"] <= 3.0


def test_no_site_is_under_water(tmp_path):
    """The sea band is y=40 against a sea level of 62 and must never be offered."""
    out = run(find_sites, W + ["--min-size", "8", "--max-slope", "3", "--top", "40"],
              tmp_path / "sites.json")
    d = load(out)
    for s in d["sites"]:
        assert s["height"]["min"] > 62.0
        assert s["min_z"] < 235 or s["max_z"] < 235


def test_sites_do_not_overlap(tmp_path):
    out = run(find_sites, W + ["--min-size", "10", "--max-slope", "3", "--top", "15"],
              tmp_path / "sites.json")
    d = load(out)
    claimed = np.zeros((256, 256), dtype=bool)
    for s in d["sites"]:
        box = claimed[s["min_z"]:s["max_z"] + 1, s["min_x"]:s["max_x"] + 1]
        assert not box.any(), "site %d overlaps an earlier one" % s["rank"]
        box[:] = True


# --------------------------------------------------------------- route_path

# (60,130) and (170,130) sit on the flat base either side of the ridge, whose
# crest at x=112 reaches y=140. Straight across is 110 blocks and 80 of climb.
ACROSS = ["--from", "60,130", "--to", "170,130", "--max-slope", "60"]


def test_zero_slope_weight_goes_straight_over_the_crest(tmp_path):
    out = run(route_path, W + ACROSS + ["--slope-weight", "0"], tmp_path / "p.json")
    d = load(out)
    assert d["stats"]["detour_ratio"] == pytest.approx(1.0, abs=0.01)
    assert d["stats"]["length_blocks"] == pytest.approx(110.0, abs=0.01)
    assert d["stats"]["max_y"] == pytest.approx(140.0, abs=0.01)
    assert d["stats"]["total_climb"] == pytest.approx(80.0, abs=0.01)


def test_high_slope_weight_contours_around_the_ridge(tmp_path):
    """Paying 12 per block of climb makes 80 blocks of climb cost more than the detour."""
    out = run(route_path, W + ACROSS + ["--slope-weight", "12"], tmp_path / "p.json")
    d = load(out)
    assert d["stats"]["max_y"] == pytest.approx(100.0, abs=0.01), "must not climb the ridge"
    assert d["stats"]["total_climb"] == pytest.approx(0.0, abs=0.01)
    assert d["stats"]["detour_ratio"] > 1.4
    assert d["stats"]["length_blocks"] > 110.0


def test_path_endpoints_and_continuity(tmp_path):
    out = run(route_path, W + ACROSS + ["--slope-weight", "4"], tmp_path / "p.json")
    d = load(out)
    line = d["polyline"]
    assert line[0] == [60, 130] and line[-1] == [170, 130]
    for (x1, z1), (x2, z2) in zip(line, line[1:]):
        assert max(abs(x2 - x1), abs(z2 - z1)) > 0


def test_router_refuses_to_enter_water(tmp_path):
    """A goal in the sea band is unreachable unless water is explicitly allowed."""
    with pytest.raises(SystemExit):
        route_path.main(W + ["--from", "60,130", "--to", "60,245",
                             "--slope-weight", "1", "--out", str(tmp_path / "p.json")])


# --------------------------------------------------------------- sightlines


def test_ridge_blocks_the_far_side(tmp_path):
    """From (60,130) the base at (170,130) is hidden; the near flank at x=74 blocks it."""
    out = run(sightlines, W + ["--from", "60,130", "--eye", "2",
                               "--target", "far_base:170,130"], tmp_path / "s.json")
    r = load(out)["results"][0]
    assert r["visible"] is False
    assert r["blocked_at"]["ground_y"] == pytest.approx(102.0, abs=0.2)
    assert r["blocked_at"]["x"] == pytest.approx(74.0, abs=1.0)


def test_crest_itself_is_visible(tmp_path):
    """A target on the summit must not be reported as occluded by its own summit."""
    out = run(sightlines, W + ["--from", "60,130", "--eye", "2",
                               "--target", "crest:112,130"], tmp_path / "s.json")
    r = load(out)["results"][0]
    assert r["visible"] is True
    assert r["distance"] == pytest.approx(52.0, abs=0.01)


def test_flat_ground_is_visible(tmp_path):
    out = run(sightlines, W + ["--from", "60,130", "--eye", "2",
                               "--target", "west:40,130"], tmp_path / "s.json")
    r = load(out)["results"][0]
    assert r["visible"] is True


def test_raising_the_target_can_clear_the_ridge(tmp_path):
    """A 60-block tower at the far base rises above the 140 crest and becomes visible."""
    out = run(sightlines, W + ["--from", "60,130", "--eye", "2",
                               "--target-height", "120",
                               "--target", "tower:170,130"], tmp_path / "s.json")
    r = load(out)["results"][0]
    assert r["visible"] is True


# -------------------------------------------------------------- slope_masks


def test_masks_written_with_expected_pixels(tmp_path):
    assert slope_masks.main(W + ["--out", str(tmp_path), "--max-degrees", "60"]) == 0
    slope = np.array(Image.open(tmp_path / "slope.png"))
    land = np.array(Image.open(tmp_path / "land.png"))
    aspect = np.array(Image.open(tmp_path / "aspect.png"))

    assert slope.shape == (256, 256) and slope.dtype == np.uint8
    assert slope[80, 20] == 0, "flat base must be zero slope"
    # a 45 degree flank scaled against a 60 degree ceiling: 45/60*255 = 191.25
    assert slope[130, 100] == pytest.approx(191, abs=1)

    assert land[80, 20] == 255, "base is above sea level"
    assert land[240, 100] == 0, "sea band is below sea level"

    # west-facing flank: 270 degrees scaled to 0..255 is 192
    assert aspect[130, 100] == pytest.approx(192, abs=1)
    assert aspect[80, 20] == 0, "flat ground has no aspect"


def test_masks_record_their_source(tmp_path):
    slope_masks.main(W + ["--out", str(tmp_path)])
    d = load(tmp_path / "masks.json")
    world = T.load_world(FIXTURE / "world.json")
    assert d["source"]["heightmap_sha256"] == world["heightmap"]["sha256"]
    assert d["land_fraction"] == pytest.approx(235.0 / 256.0, abs=1e-4)


# ------------------------------------------------------- the blocked guard


def test_explicit_heightmap_cannot_bypass_the_hash_check(tmp_path):
    """--heightmap must be verified against the recorded sha256, not trusted."""
    forged = tmp_path / "forged.png"
    data = bytearray((FIXTURE / "land_fixture.png").read_bytes())
    data[-20] ^= 0xFF  # corrupt one byte inside the image data
    forged.write_bytes(bytes(data))
    with pytest.raises(T.TerrainUnavailable, match="sha256 mismatch"):
        T.load(FIXTURE / "world.json", heightmap=forged)


def test_explicit_heightmap_accepts_the_verified_file():
    h, _ = T.load(FIXTURE / "world.json", heightmap=FIXTURE / "land_fixture.png")
    assert h.shape == (256, 256)


@pytest.mark.parametrize("mod,args", [
    (find_sites, []),
    (route_path, ["--from", "1,1", "--to", "2,2"]),
    (sightlines, ["--from", "1,1", "--target", "t:2,2"]),
    (slope_masks, []),
])
def test_every_tool_refuses_the_real_blocked_heightmap(mod, args, tmp_path, capsys, monkeypatch):
    """Without a source root the real heightmap cannot be verified; no tool may produce output."""
    monkeypatch.delenv("COBBLERS_SOURCE_ROOT", raising=False)
    with pytest.raises(SystemExit) as exc:
        mod.main(args + ["--out", str(tmp_path / "nope")])
    assert "terrain unavailable" in str(exc.value)
    assert not (tmp_path / "nope").exists()
