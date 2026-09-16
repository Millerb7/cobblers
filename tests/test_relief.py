"""Hillside relief (tools/sculpt.py unit_noise, sculpt_relief, and the relief stage of run()) and the terracing
measure (tools/terrace_measure.py run).

Everything runs on synthetic heightmaps with the relief settings from data/sculpt.json (read only), so the
amplitude, fade and calibration assertions follow the configured values rather than copies of them. The locality
test runs at 1100 blocks (above 1024 + stretch + 2, where the fixed 1024-block noise window is taken from the map's own
draw) and at 512 blocks (below it, where the window comes from a separate noise draw of that size).

Not covered: whether the relief reads as spurs and gullies in game or in WorldPainter, the relief on the real
8192-block heightmap (the commit message records its whole-map measurements), and terrace_measure's coast and
by-region sections.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sculpt as S  # noqa: E402
import terrace_measure as TM  # noqa: E402

SEA = 62
SCULPT = json.loads((ROOT / "data" / "sculpt.json").read_text(encoding="utf-8"))
RELIEF = SCULPT["relief"]
K, CAP, CLIP = RELIEF["amplitude_per_grade"], RELIEF["max_amplitude_blocks"], RELIEF["noise_soft_clip_sigma"]
MEASURE_WORLD = {"vertical": {"sea_level": SEA}, "import": {"water_level": SEA}}


def _ramp(n, grade, base, axis=1):
    x = np.arange(n, dtype=np.float32)
    line = base + grade * x
    return np.tile(line, (n, 1)).astype(np.float32) if axis == 1 else np.tile(line[:, None], (1, n)).astype(np.float32)


def _triangle(n, grade, lo, period):
    """Ridges and valleys along x: grade on every flank, from lo to lo + grade * period / 2."""
    x = np.arange(n, dtype=np.float32)
    ph = np.mod(x, period)
    tri = np.where(ph < period / 2, ph, period - ph) * grade + lo
    return np.tile(tri, (n, 1)).astype(np.float32)


# ------------------------------------------------------------------ unit_noise

# removing this lets the relief noise drift in mean or scale between octaves or seeds, so amplitude_per_grade no
# longer means what the calibration measured
def test_unit_noise_is_zero_mean_unit_variance_and_seeded():
    for spacing in (12, 24, 48):
        a = S.unit_noise(512, spacing, 7)
        assert a.shape == (512, 512) and a.dtype == np.float32
        assert abs(float(a.mean())) < 1e-3 and abs(float(a.std()) - 1) < 1e-3
        assert np.array_equal(a, S.unit_noise(512, spacing, 7))
        assert not np.array_equal(a, S.unit_noise(512, spacing, 8))
    # smooth at its spacing: neighbours are far more alike than points a spacing apart
    a = S.unit_noise(512, 24, 1)
    near = np.corrcoef(a[:, :-1].ravel(), a[:, 1:].ravel())[0, 1]
    far = np.corrcoef(a[:, :-48].ravel(), a[:, 48:].ravel())[0, 1]
    assert near > 0.95 and abs(far) < 0.3


# ------------------------------------------------------------------ sculpt_relief

# removing this lets relief roughen flat ground (towns, meadows, lake shores), which must stay flat
def test_flat_ground_is_unchanged():
    h = np.full((256, 256), 100.0, np.float32)
    assert np.array_equal(S.sculpt_relief(h, RELIEF, SEA, 3), h)


# removing this lets the relief amplitude stop following the regional grade (A = k * g) or exceed its cap times the
# soft clip, which is what bounds the largest change a column can take
def test_amplitude_scales_with_grade_and_is_bounded():
    n = 512
    inner = (slice(80, 430), slice(80, 430))                  # away from the smoothing's edge effects
    d1 = S.sculpt_relief(_ramp(n, 0.05, 100), RELIEF, SEA, 3) - _ramp(n, 0.05, 100)
    d2 = S.sculpt_relief(_ramp(n, 0.10, 100), RELIEF, SEA, 3) - _ramp(n, 0.10, 100)
    assert np.allclose(d2[inner], 2 * d1[inner], atol=2e-3), "twice the grade, twice the relief"
    assert np.abs(d1).max() <= K * 0.05 * CLIP + 1e-3
    assert np.abs(d1[inner]).max() > K * 0.05 * 0.8, "the relief is not negligible"
    steep = _triangle(n, 0.45, 80, 360)                       # K * 0.45 = 4.5 > the cap
    d3 = S.sculpt_relief(steep, RELIEF, SEA, 3) - steep
    assert np.abs(d3).max() <= CAP * CLIP + 1e-3
    assert np.abs(d3).max() > CAP, "the cap binds, the soft clip allows up to CLIP times it"


# removing this lets relief reach the shore band just above sea level or break up cliffs
def test_relief_fades_out_near_sea_level_and_on_steep_ground():
    n = 512
    lo, hi = RELIEF["low_fade_above_sea"]
    h = _ramp(n, 0.2, 30)                                     # y30 to y132 along x
    d = S.sculpt_relief(h, RELIEF, SEA, 3) - h
    low = h < SEA + lo
    assert low[80:430, 80:430].any()
    assert (d[low] == 0).all()
    assert np.abs(d[(h > SEA + hi) & (np.arange(n)[None, :] < 430)]).max() > 0.5
    s0, s1 = RELIEF["steep_fade_grade"]
    cliff = _triangle(n, s1 * 1.2, 15, 300)                   # flanks of grade 1.2 x steep_fade[1], y15 to y195
    cliff = np.minimum(cliff, 199.0)
    dc = S.sculpt_relief(cliff, RELIEF, SEA, 3) - cliff
    x = np.arange(n)
    mid = (np.abs(np.mod(x, 300) - 75) <= 10) | (np.abs(np.mod(x, 300) - 225) <= 10)   # the middle of each flank
    sel = mid[None, :] & (cliff > SEA + hi) & (cliff < 190)
    assert sel.any()
    assert (dc[sel] == 0).all()
    assert np.abs(dc).max() > 0.1, "gentler ground at ridges and valleys still gets relief"


LOCAL_N = 1100                                                 # > 1024 + stretch + 2: the noise-only normalisation


def _hills(n):
    zz, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    return (110 + 40 * np.sin(2 * np.pi * xx / 600) * np.sin(2 * np.pi * zz / 700)).astype(np.float32)


# removing this lets a local terrain edit change the relief everywhere (as global mean/std normalisation of the
# fall-line noise did before f32f1de: every column moved by up to 0.03 blocks here), so a small fix to the authored
# heightmap would rewrite the whole import
def test_a_local_edit_changes_relief_only_near_the_edit():
    h = _hills(LOCAL_N)
    edited = h.copy()
    edited[300:700, 300:700] = 120.0                           # flatten a block: its noise is no longer averaged
    a = S.sculpt_relief(h, RELIEF, SEA, 5)
    b = S.sculpt_relief(edited, RELIEF, SEA, 5)
    reach = 3 * RELIEF["regional_sigma_blocks"]
    outside = np.ones(h.shape, bool)
    outside[300 - reach:700 + reach, 300 - reach:700 + reach] = False
    assert np.array_equal(a[outside], b[outside])
    assert np.abs(a - b)[~outside].max() > 1.0, "the edit itself changes the relief around it"


# removing this lets maps no larger than 1024 + fall_line_stretch_blocks + 2 blocks (crops, test maps) normalise the
# relief by their own fall-line noise again, so a local edit changes every column there (about 2e-4 blocks at 512)
def test_a_local_edit_changes_relief_only_near_the_edit_on_a_small_map():
    n = 512
    h = _hills(n)
    edited = h.copy()
    edited[150:300, 150:300] = 120.0
    a = S.sculpt_relief(h, RELIEF, SEA, 5)
    b = S.sculpt_relief(edited, RELIEF, SEA, 5)
    reach = 3 * RELIEF["regional_sigma_blocks"]
    outside = np.ones(h.shape, bool)
    outside[150 - reach:300 + reach, 150 - reach:300 + reach] = False
    assert np.array_equal(a[outside], b[outside])


# removing this lets the relief miss its calibration: rho on a smooth ramp should rise from about 0 to the range the
# relief was tuned for (median 0.45 on the calibration crops; about 0.4 on a 1:5 ramp)
def test_relief_raises_rho_on_a_smooth_ramp_into_the_calibrated_range():
    ramp = _ramp(512, 0.2, 70)
    before = TM.run(ramp, MEASURE_WORLD, None, False)["perturbation"]["median"]
    after = TM.run(S.sculpt_relief(ramp, RELIEF, SEA, 5), MEASURE_WORLD, None, False)["perturbation"]["median"]
    assert before < 0.02
    assert 0.35 <= after <= 0.6, after


# ------------------------------------------------------------------ relief inside run(): keep = 0

@pytest.fixture(scope="module")
def relief_run():
    h = _hills(LOCAL_N)
    cfg = {"prevailing_wind_from_deg": 250,
           "protect": dict(SCULPT["protect"], rectangles=[{"id": "home_rect", "min_x": 700, "min_z": 150,
                                                            "max_x": 800, "max_z": 400}]),
           "coast": copy.deepcopy(SCULPT["coast"]), "massifs": [],
           "volcano": dict(SCULPT["volcano"], cones=[dict(SCULPT["volcano"]["cones"][0], centre=[100, 100])]),
           "pads": [], "relief": RELIEF}
    towns = {"towns": [{"id": "town", "centre": {"x": 300, "z": 300},
                        "footprint": {"min_x": 250, "min_z": 260, "max_x": 350, "max_z": 340}}]}
    landmarks = {"landmarks": [{"id": "lake", "water_body": {"level_y": 100, "basin_polygons": [
        [[500, 700], [640, 700], [640, 820], [500, 820]]]}}]}
    world = {"vertical": {"sea_level": SEA}, "import": {"low_out": 10.093458, "high_out": 200},
             "heightmap": {"bit_depth": 16}}
    with pytest.MonkeyPatch.context() as mp:
        # the volcano stage needs a cone to box itself; it is not under test, so it returns the terrain unchanged
        mp.setattr(S, "sculpt_volcano", lambda hh, *a, **k: hh)
        new, rows, class_map, report = S.run(h, world, cfg, {"regions": [], "subregions": []},
                                             {"courses": [], "cut": {}}, towns, {}, landmarks)
    return h, new, report


SITES = {"footprint": (slice(260, 341), slice(250, 351)), "protect_rectangle": (slice(150, 401), slice(700, 801)),
         "lake_basin": (slice(700, 821), slice(500, 641))}


# removing this lets relief move columns inside protected footprints, the hometown-style protect rectangle or lake
# basins, which apply must write back bit-identical (the placed town and the basins' levels depend on them)
@pytest.mark.parametrize("site", sorted(SITES))
def test_run_relief_leaves_protected_sites_bit_identical(relief_run, site):
    h, new, report = relief_run
    sl = SITES[site]
    assert np.array_equal(new[sl], h[sl])
    z, x = sl
    around = (slice(max(0, z.start - 150), z.stop + 150), slice(max(0, x.start - 150), x.stop + 150))
    assert np.abs(new[around] - h[around]).max() > 1.0, "relief is active around the site"


# removing this lets the run report stop describing the relief stage it applied
def test_run_reports_the_relief_stage(relief_run):
    h, new, report = relief_run
    r = report["relief"]
    assert r["columns_changed_half_block"] > 0
    assert 0 < r["max_raise"] <= CAP * CLIP + 0.01 and -CAP * CLIP - 0.01 <= r["max_lower"] < 0


# ------------------------------------------------------------------ terrace_measure.run

def _measure(h):
    return TM.run(h.astype(np.float32), MEASURE_WORLD, None, False)


# removing this lets the measure misread a perfectly regular ring field: a uniform 1:3 ramp has treads of exactly 3
# blocks, no tread variation and no grade perturbation
def test_terrace_measure_on_a_uniform_1_in_3_ramp():
    r = _measure(_ramp(512, 1 / 3, 63))
    assert r["regimes"]["ring_1_12_to_1_1.5"] == 1.0
    assert r["treads"]["median"] == 3.0 and r["treads"]["count"] > 1000
    assert r["tread_cv"]["median"] < 0.01 and r["tread_cv"]["windows"] > 20
    assert r["perturbation"]["median"] < 0.01


# removing this lets the measure stop registering broken rings: 1.5 blocks of relief at a 32-block wavelength on a
# 1:3 ramp puts rho near 0.5 and the tread variation above 0.5
def test_terrace_measure_on_a_ramp_with_relief():
    zz, xx = np.mgrid[0:512, 0:512].astype(np.float32)
    h = 63 + xx / 3 + 1.5 * np.sin(2 * np.pi * xx / 32) * np.sin(2 * np.pi * zz / 32)
    r = _measure(h)
    assert 0.4 <= r["perturbation"]["median"] <= 0.6, r["perturbation"]["median"]
    assert r["tread_cv"]["median"] > 0.5, r["tread_cv"]["median"]


# removing this lets a histogram drop or double-count a bin (shares are rounded to 4 places, so they sum to 1 within
# the rounding of 7-9 bins)
@pytest.mark.parametrize("which", ["ramp", "relief"])
def test_terrace_measure_histograms_sum_to_one(which):
    zz, xx = np.mgrid[0:512, 0:512].astype(np.float32)
    h = 63 + xx / 3 + (1.5 * np.sin(2 * np.pi * xx / 32) * np.sin(2 * np.pi * zz / 32) if which == "relief" else 0)
    r = _measure(h)
    for key in ("treads", "tread_cv", "perturbation", "terrace_index"):
        hist = r[key]["histogram"]
        assert len(hist) >= 7 and abs(sum(hist.values()) - 1.0) <= 5e-4 * len(hist), (key, sum(hist.values()))
