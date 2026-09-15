"""check_sculpt in tools/validate_data.py: data/sculpt.json essentials and references, and the import chain recorded in
world.json heightmap.sculpted_from.

Each rule has a passing baseline and a minimal breaking change. The fixture is a synthetic data directory in tmp_path
(world.json with bounds, import range and sculpted_from; rivers.json with a cut output; regions.json; towns.json;
sculpt.json). The last test runs the check on the real data/ (read only). The river-cut side of the chain
(check_rivers) is tested in tests/test_river_character.py.

Not covered: whether the recorded sha256 values match the files on disk (the integrity check hashes only the imported
heightmap), whether the sculpt looks right, and whether every numeric setting is sensible beyond keeping
tools/sculpt.py's arithmetic finite.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import validate_data as V  # noqa: E402

CUT, SCULPTED = "c" * 64, "d" * 64
BEACHLIKE = {"grade": [8, 15], "berm_blocks": [6, 18], "top_above_sea": [3.0, 5.5], "back_blocks": [40, 110],
             "shelf_grade": [12, 20], "shelf_depth": [3.5, 6], "micro_relief": 0.25}


def _sculpt():
    return {
        "schema": "cobblers.sculpt/1",
        "prevailing_wind_from_deg": 250,
        "protect": {"settlement_margin_blocks": 32, "landmark_tree_margin_blocks": 8, "river_margin_blocks": 12,
                    "lake_margin_blocks": 16, "feather_blocks": 24, "terrain_feather_blocks": 60},
        "coast": {
            "band_blocks": 300, "spacing_blocks": 32, "concavity_radius_blocks": 256, "fetch_cap_blocks": 3000,
            "estuary_mouth_radius_blocks": 200, "class_smoothing_radius_blocks": 128, "micro_relief_scale_blocks": 20,
            "hard_regions": ["peaks"], "soft_regions": ["dunes"], "rules": ["text"],
            "classes": {
                "beach": dict(BEACHLIKE), "estuary": dict(BEACHLIKE),
                "shore": {k: v for k, v in BEACHLIKE.items() if k != "berm_blocks"},
                "rocky": {"bank_grade": 1.8, "bank_top_above_sea": 7.0, "back_blocks": 50, "drop_grade": 1.4,
                          "drop_depth": 9, "rugged": 1.0, "micro_relief": 0.9},
                "cliff": {"height": [10, 26], "relief_share": 0.35, "face_blocks": [1, 7], "back_blocks": [35, 110],
                          "talus_blocks": 7, "drop_grade": 0.9, "drop_depth": 16, "micro_relief": 0.9},
            },
        },
        "massifs": [{
            "id": "range", "subregions": ["peak_a", "peak_b"], "steep_faces_deg": 60, "shift_blocks": 140,
            "shift_taper_blocks": 320, "shift_from_y": 110,
            "summits": {"base_y": 176, "rise": 24, "ridge_scale_blocks": 170, "highest": [500, 400], "secondary_cap": 0.75},
            "strata": {"from_y": 130, "cliff_slope_deg": 32, "cliff_band": [13, 19], "cliff_strength": 0.45,
                       "bench_slope_deg": [12, 26], "bench_band": [22, 32], "bench_strength": 0.22},
        }],
        "volcano": {
            "steep_faces_deg": 250, "shift_blocks": 25, "shift_taper_blocks": 260, "shift_from_y": 135,
            "cones": [
                {"id": "great", "form": "stratovolcano", "centre": [600, 600], "crater_radius": 48, "crater_floor_y": 174,
                 "rim_y": 200, "rim_width": 14, "flank_to_radius": 240, "flank_drop": 35, "breach_bearing_deg": 90,
                 "breach_half_angle_deg": 28, "breach_floor_y": 176, "breach_grade": 0.15},
                {"id": "dome", "form": "lava_dome", "centre": [700, 500], "dome_radius": 70, "dome_top_y": 199,
                 "dome_drop": 12, "spines": 5, "spine_radius": 4},
                {"id": "cinder", "form": "cinder_cone", "centre": [650, 700], "top_y": 189, "slope": 0.62, "radius": 75,
                 "crater_radius": 14, "crater_floor_y": 180, "strength": 0.7, "plain_y": 145},
                {"id": "caldera", "form": "caldera", "centre": [800, 650], "floor_radius": 70, "floor_y": 104,
                 "wall_to_radius": 92, "rim_to_radius": 106, "rim_y": 150, "rim_noise": 4, "flank_to_radius": 195,
                 "flank_grade": 0.2},
            ],
        },
        "relief": {"regional_sigma_blocks": 24, "octaves": [{"spacing_blocks": 12, "weight": 0.5},
                                                      {"spacing_blocks": 24, "weight": 1.0}],
                   "fall_line_stretch_blocks": 16, "fall_line_taps": 9, "amplitude_per_grade": 10,
                   "max_amplitude_blocks": 2.5, "noise_soft_clip_sigma": 2.0, "low_fade_above_sea": [4, 12],
                   "steep_fade_grade": [0.7, 1.0], "protect_feather_blocks": 24},
        "pads": [{"site": "scar", "y": 194, "radius": 150, "feather": 140}],
    }


def _world():
    return {"schema": "cobblers.world/1", "bounds": {"min_x": 0, "min_z": 0, "max_x": 999, "max_z": 999},
            "import": {"low_out": 10.09, "high_out": 200},
            "heightmap": {"path": "sculpted.png", "sha256": SCULPTED,
                          "sculpted_from": {"path": "cut.png", "sha256": CUT, "generator": "tools/sculpt.py apply"},
                          "derived_from": {"path": "base.png", "sha256": "a" * 64}}}


def build(tmp_path, sculpt=None, world=None, rivers=None, regions=None, towns=None, skip=()):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    files = {
        "world.json": world if world is not None else _world(),
        "rivers.json": rivers if rivers is not None else {"schema": "cobblers.rivers/1", "courses": [],
                                                          "cut": {"output": {"path": "cut.png", "sha256": CUT}}},
        "regions.json": regions if regions is not None else {
            "regions": [{"id": "peaks"}, {"id": "dunes"}], "subregions": [{"id": "peak_a"}, {"id": "peak_b"}]},
        "towns.json": towns if towns is not None else {"schema": "cobblers.towns/1", "towns": [
            {"id": "scar", "centre": {"x": 480, "z": 420}}]},
        "sculpt.json": sculpt if sculpt is not None else _sculpt(),
    }
    for name, doc in files.items():
        if name not in skip:
            (d / name).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return d


def run(d):
    ctx = V.Context(d, None, V.Report())
    V.check_schema(ctx)
    V.check_sculpt(ctx)
    return ctx.report.findings


def of(findings, severity):
    return [f.message for f in findings if f.check == "sculpt" and f.severity == severity]


def errors_for(tmp_path, mutate):
    s, w, t = _sculpt(), _world(), {"schema": "cobblers.towns/1", "towns": [{"id": "scar", "centre": {"x": 480, "z": 420}}]}
    mutate(s, w, t)
    return of(run(build(tmp_path, sculpt=s, world=w, towns=t)), V.ERROR)


# ------------------------------------------------------------------ baseline and registration

# removing this lets every breaking-change test below pass on a fixture that was already failing
def test_baseline_fixture_is_clean(tmp_path):
    findings = run(build(tmp_path))
    assert of(findings, V.ERROR) == [] and of(findings, V.WARNING) == [] and of(findings, V.SKIPPED) == []
    assert of(findings, V.INFO) == ["checked 1 massifs, 4 volcano cones and 1 pads"]


# removing this lets check_sculpt fall out of the CLI's CHECKS list unnoticed
def test_cli_runs_the_sculpt_check(tmp_path, capsys):
    s = _sculpt()
    s["volcano"]["cones"][0]["form"] = "shield"
    d = build(tmp_path, sculpt=s)
    assert "sculpt" in [name for name, _ in V.CHECKS]
    V.main(["--data", str(d), "--only", "sculpt", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert any(f["check"] == "sculpt" and "shield" in f["message"] for f in out["findings"])


# removing this lets the real sculpt configuration and import chain drift without the validator noticing
def test_real_sculpt_data_passes():
    ctx = V.Context(ROOT / "data", None, V.Report())
    V.check_schema(ctx)
    V.check_sculpt(ctx)
    bad = [f.message for f in ctx.report.findings if f.check == "sculpt" and f.severity in (V.ERROR, V.WARNING, V.SKIPPED)]
    assert bad == []


# ------------------------------------------------------------------ absent and malformed files

# removing this lets a missing data/sculpt.json pass silently instead of being reported as not checked
def test_absent_sculpt_is_skipped_with_a_reason(tmp_path):
    w = _world()
    del w["heightmap"]["sculpted_from"]
    findings = run(build(tmp_path, world=w, skip=("sculpt.json",)))
    assert of(findings, V.ERROR) == []
    assert len(of(findings, V.SKIPPED)) == 1 and "data/sculpt.json is absent" in of(findings, V.SKIPPED)[0]


# removing this lets world.json claim a sculpt that has no configuration in the repository
def test_sculpted_from_without_sculpt_json_is_an_error(tmp_path):
    errs = of(run(build(tmp_path, skip=("sculpt.json",))), V.ERROR)
    assert len(errs) == 1 and "sculpted_from records a sculpt but data/sculpt.json is absent" in errs[0]


# removing this lets a missing rivers, regions or towns file quietly disable part of the check
@pytest.mark.parametrize("skip,needle", [
    ("rivers.json", "data/rivers.json is absent"),
    ("regions.json", "data/regions.json is absent"),
    ("towns.json", "data/towns.json is absent"),
])
def test_absent_dependency_is_skipped_not_passed(tmp_path, skip, needle):
    skipped = of(run(build(tmp_path, skip=(skip,))), V.SKIPPED)
    assert len(skipped) == 1 and needle in skipped[0], skipped


# removing this lets a corrupt sculpt.json be skipped (fail open) instead of failing
def test_malformed_sculpt_json_is_an_error(tmp_path):
    d = build(tmp_path)
    (d / "sculpt.json").write_text("{nope", encoding="utf-8")
    assert any("invalid JSON" in m for m in of(run(d), V.ERROR))


# ------------------------------------------------------------------ the import chain

# removing this lets world.json import a sculpt that was not made from the recorded river cut, overwrite the cut file,
# or leave the sculpt input unrecorded
@pytest.mark.parametrize("mutate,needle", [
    (lambda s, w, t: w["heightmap"].pop("sculpted_from"), "heightmap.sculpted_from is absent"),
    (lambda s, w, t: w["heightmap"]["sculpted_from"].update(sha256="e" * 64), "is not the river cut output"),
    (lambda s, w, t: w["heightmap"]["sculpted_from"].update(path="other.png"), "is not the river cut output path"),
    (lambda s, w, t: w["heightmap"].update(path="cut.png"), "is also its sculpted_from path"),
    (lambda s, w, t: w["heightmap"]["sculpted_from"].pop("sha256"), "needs a path and a 64-hex sha256"),
])
def test_import_chain_breaks_are_errors(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# removing this lets a sculpt that changed nothing (same sha as its input) pass without comment
def test_sculpt_identical_to_its_input_warns(tmp_path):
    w = _world()
    w["heightmap"]["sha256"] = CUT
    findings = run(build(tmp_path, world=w))
    assert of(findings, V.ERROR) == [] and any("changed nothing" in m for m in of(findings, V.WARNING))


# ------------------------------------------------------------------ schema essentials

# removing this lets a setting tools/sculpt.py reads be missing, of the wrong type, or a range that makes its
# arithmetic divide by zero
@pytest.mark.parametrize("mutate,needle", [
    (lambda s, w, t: s.update(schema="cobblers.sculpt/0"), 'expected "cobblers.sculpt/1"'),
    (lambda s, w, t: s.update(prevailing_wind_from_deg=360), "prevailing_wind_from_deg must be a bearing"),
    (lambda s, w, t: s["protect"].pop("feather_blocks"), "protect.feather_blocks must be a number > 0"),
    (lambda s, w, t: s["protect"].update(river_margin_blocks=-1), "protect.river_margin_blocks must be a number >= 0"),
    (lambda s, w, t: s["coast"].update(band_blocks=0), "coast.band_blocks must be a number > 0"),
    (lambda s, w, t: s["coast"].pop("micro_relief_scale_blocks"), "coast.micro_relief_scale_blocks"),
    (lambda s, w, t: s["coast"]["classes"].pop("estuary"), "coast.classes must define exactly"),
    (lambda s, w, t: s["coast"]["classes"].update(lagoon={}), "coast.classes must define exactly"),
    (lambda s, w, t: s["coast"]["classes"]["beach"].update(grade=[0, 15]), "coast.classes.beach.grade"),
    (lambda s, w, t: s["coast"]["classes"]["beach"].update(back_blocks=[110, 40]), "coast.classes.beach.back_blocks"),
    (lambda s, w, t: s["coast"]["classes"]["cliff"].update(face_blocks=[7, 7]), "coast.classes.cliff.face_blocks"),
    (lambda s, w, t: s["coast"]["classes"]["rocky"].update(drop_grade=0), "coast.classes.rocky.drop_grade"),
    (lambda s, w, t: s["coast"].update(soft_regions=["dunes", "peaks"]), 'region "peaks" is both a hard and a soft'),
    (lambda s, w, t: s["massifs"][0].update(shift_taper_blocks=0), "massifs.range.shift_taper_blocks"),
    (lambda s, w, t: s["massifs"][0]["summits"].update(secondary_cap=1.5), "massifs.range.summits.secondary_cap"),
    (lambda s, w, t: s["massifs"][0]["summits"].update(highest=[500]), "massifs.range.summits.highest must be [x, z]"),
    (lambda s, w, t: s["massifs"][0]["strata"].update(cliff_band=[0, 19]), "massifs.range.strata.cliff_band"),
    (lambda s, w, t: s["massifs"][0].update(subregions=[]), "massifs.range.subregions must be a non-empty list"),
    (lambda s, w, t: s["massifs"].append(copy.deepcopy(s["massifs"][0])), 'duplicate massif "range"'),
    (lambda s, w, t: s["volcano"].update(cones=[]), "volcano.cones must be a non-empty list"),
    (lambda s, w, t: s["volcano"]["cones"][1].update(form="shield"), "volcano.cones.dome.form 'shield' is not one of"),
    (lambda s, w, t: s["volcano"]["cones"][1].pop("spine_radius"), "volcano.cones.dome.spine_radius"),
    (lambda s, w, t: s["volcano"]["cones"][1].update(spines=2.5), "volcano.cones.dome.spines must be an integer"),
    (lambda s, w, t: s["volcano"]["cones"][2].update(crater_radius=80), "crater_radius must be below radius"),
    (lambda s, w, t: s["volcano"]["cones"][0].update(flank_to_radius=60), "flank_to_radius must exceed"),
    (lambda s, w, t: s["volcano"]["cones"][3].update(wall_to_radius=70), "floor_radius < wall_to_radius"),
    (lambda s, w, t: s["volcano"]["cones"][3].pop("centre"), "volcano.cones.caldera.centre must be [x, z]"),
    (lambda s, w, t: s["volcano"]["cones"].append(copy.deepcopy(s["volcano"]["cones"][0])), 'duplicate cone "great"'),
    (lambda s, w, t: s["pads"][0].update(feather=0), "pads.scar.feather must be a number > 0"),
    (lambda s, w, t: s["pads"][0].update(y=240), "pads.scar.y 240 is outside the import range"),
    (lambda s, w, t: s["pads"].append(dict(s["pads"][0])), 'pad site "scar" is listed twice'),
])
def test_schema_breaks_are_errors(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# ------------------------------------------------------------------ references

# ------------------------------------------------------------------ hillside relief

# removing this lets a relief setting tools/sculpt.py sculpt_relief reads be missing, of the wrong type, or a value
# that zeroes the relief, divides by zero (soft clip, smoothsteps, noise spacing) or samples the fall line one-sided
@pytest.mark.parametrize("mutate,needle", [
    (lambda s, w, t: s["relief"].pop("regional_sigma_blocks"), "relief.regional_sigma_blocks must be a number > 0"),
    (lambda s, w, t: s["relief"].update(noise_soft_clip_sigma=0), "relief.noise_soft_clip_sigma must be a number > 0"),
    (lambda s, w, t: s["relief"].update(fall_line_taps=1), "relief.fall_line_taps must be an integer >= 2"),
    (lambda s, w, t: s["relief"].update(fall_line_taps=9.0), "relief.fall_line_taps must be an integer >= 2"),
    (lambda s, w, t: s["relief"].update(fall_line_stretch_blocks=-1), "relief.fall_line_stretch_blocks must be a number >= 0"),
    (lambda s, w, t: s["relief"].update(amplitude_per_grade="ten"), "relief.amplitude_per_grade must be a number >= 0"),
    (lambda s, w, t: s["relief"].pop("max_amplitude_blocks"), "relief.max_amplitude_blocks must be a number >= 0"),
    (lambda s, w, t: s["relief"].update(low_fade_above_sea=[12, 4]), "relief.low_fade_above_sea must be [lo, hi] with lo < hi"),
    (lambda s, w, t: s["relief"].update(low_fade_above_sea=[-3, 12]), "must start at or above sea level"),
    (lambda s, w, t: s["relief"].update(steep_fade_grade=[1.0, 1.0]), "relief.steep_fade_grade must be [lo, hi] with lo < hi"),
    (lambda s, w, t: s["relief"].update(steep_fade_grade=[0, 1.0]), "relief.steep_fade_grade must be above grade 0"),
    (lambda s, w, t: s["relief"].update(protect_feather_blocks=0), "relief.protect_feather_blocks must be a number > 0"),
    (lambda s, w, t: s["relief"].update(octaves=[]), "relief.octaves must be a non-empty list"),
    (lambda s, w, t: s["relief"]["octaves"][0].update(spacing_blocks=0), "relief.octaves[0].spacing_blocks must be an integer >= 1"),
    (lambda s, w, t: s["relief"]["octaves"][1].pop("weight"), "relief.octaves[1].weight must be a number >= 0"),
    (lambda s, w, t: [o.update(weight=0) for o in s["relief"]["octaves"]], "relief.octaves weights are all 0"),
    (lambda s, w, t: s.update(relief=[1, 2]), "relief must be an object"),
])
def test_relief_breaks_are_errors(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# removing this lets a sculpt configuration without a relief block be refused, although run() treats it as optional
def test_relief_block_is_optional(tmp_path):
    s = _sculpt()
    del s["relief"]
    assert of(run(build(tmp_path, sculpt=s)), V.ERROR) == []


# removing this lets the real relief settings drift from what the validator accepts
def test_real_relief_settings_pass_the_relief_rules():
    real = json.loads((ROOT / "data" / "sculpt.json").read_text(encoding="utf-8"))["relief"]
    for k, kind in V.SCULPT_RELIEF.items():
        assert V._kind_ok(real[k], kind), (k, real[k])


# removing this lets a coast region, massif sub-region or pad site name something that does not exist, so the sculpt
# silently skips it (regions never match, the massif mask is empty and run() crashes, or the pad KeyErrors)
@pytest.mark.parametrize("mutate,needle", [
    (lambda s, w, t: s["coast"]["hard_regions"].append("tri_peeks"), 'coast.hard_regions names "tri_peeks"'),
    (lambda s, w, t: s["coast"]["soft_regions"].append("peak_a"), 'coast.soft_regions names "peak_a", which is not a region'),
    (lambda s, w, t: s["massifs"][0]["subregions"].append("peaks"), '"peaks", which is not a sub-region'),
    (lambda s, w, t: s["pads"][0].update(site="the_scarr"), 'pad site "the_scarr" is not in data/towns.json'),
    (lambda s, w, t: t["towns"][0].pop("centre"), 'pad site "scar" has no centre x/z'),
])
def test_unknown_references_are_errors(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# removing this lets a designated summit or a cone centre sit off the map, where the brush does nothing or clips
@pytest.mark.parametrize("mutate,needle", [
    (lambda s, w, t: s["massifs"][0]["summits"].update(highest=[500, 1000]), "massifs.range.summits.highest (500, 1000) is outside"),
    (lambda s, w, t: s["volcano"]["cones"][2].update(centre=[-5, 700]), "volcano.cones.cinder.centre (-5, 700) is outside"),
])
def test_positions_outside_world_bounds_are_errors(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert errs == [needle + " the world bounds"], errs
