"""The independent training-grounds audit (tools/training_grounds_audit.py).

Three kinds of test:
  - its pieces on hand-computable synthetic inputs (caps, sign facing, segment and rectangle distance, the evolution
    rules, the sign parser);
  - the real records, pinned to the defects the audit found when it was written (a new failure, or a fixed one,
    changes the set and fails the test);
  - independence, by MUTATING THE GENERATOR (tools/training_grounds.py), never the data: its band(), its sign
    rotation and its route-path loader are patched, its output is fed to the audit, and the audit must fail while
    data/training_grounds.json is byte-for-byte untouched. The unmutated generator's output is the control.

Not covered: anything in a running game (the EXP clamp, the block's presence after R9E, walking to the ground);
see docs/mechanics/LEVEL_CATCHUP.md section 7 and the audit's own docstring.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import training_grounds_audit as A  # noqa: E402

DATA = ROOT / "data" / "training_grounds.json"

# The defects the audit found on 2026-10-06 (gym 8's ground is 26.2 blocks from a lower_lane lamp and 31.1 from
# lower_lane_lot_09 in derived/towns/gym8_town_plan.json, under the 32 docs/mechanics/LEVEL_CATCHUP.md section 7.4
# asks). Fixing it, or a new failure, changes this set.
KNOWN_FAILS = {("training_ground_gym8", "building_clearance")}


# ------------------------------------------------------------------------------------------------ synthetic pieces
def _trainers(aces, tops=None, rel=0):
    tops = tops or aces
    return {"generation_contract": {"gym_ace_levels": aces, "relative_level_cap": rel},
            "trainers": [{"class": "gym_leader", "order": i + 1, "team": [{"level": t - 3}, {"level": t}]}
                         for i, t in enumerate(tops)]}


def test_cap_is_ace_plus_relative_never_under_initial():
    # Removing it lets a wrong cap formula (e.g. ignoring relativeLevelCap) pass every level check.
    caps, probs = A.gym_caps(_trainers([20, 25], rel=-2), "initialLevelCap = 20\nrelativeLevelCap = -2\n")
    assert caps == {1: 20, 2: 23} and probs == []
    caps, _ = A.gym_caps(_trainers([12, 25]), "initialLevelCap = 15\nrelativeLevelCap = 0\n")
    assert caps == {1: 15, 2: 25}


def test_cap_sources_disagreeing_is_a_problem():
    # Removing it lets gym_ace_levels drift from the leaders' real teams unnoticed.
    _caps, probs = A.gym_caps(_trainers([20, 25], tops=[20, 27]), "initialLevelCap = 20\nrelativeLevelCap = 0\n")
    assert len(probs) == 1 and "gym 2" in probs[0]


def test_sign_rotation_facing_follows_minecraft():
    # Removing it lets a sign facing away from its town pass.
    for rot, want in ((0, (0, 1)), (4, (-1, 0)), (8, (0, -1)), (12, (1, 0))):
        assert np.allclose(A.facing(rot), want, atol=1e-9)
    assert A.angle_between(A.facing(0), (0, 5)) == pytest.approx(0)
    assert A.angle_between(A.facing(8), (0, 5)) == pytest.approx(180)


def test_path_distance_is_to_segments_not_vertices():
    # Removing it lets a sparse polyline's mid-segment pass within the clearance unseen (vertex distance 5.83 here).
    assert A.seg_distance(5, 3, np.array([[0, 0], [10, 0]], float)) == pytest.approx(3)


def test_rect_distance_is_zero_inside_and_euclidean_outside():
    # Removing it lets a block inside a footprint read as clear.
    assert A.rect_distance(5, 5, 0, 0, 10, 10) == 0
    assert A.rect_distance(13, 14, 0, 0, 10, 10) == pytest.approx(5)


SPECIES = {
    "a": {"preEvolution": None, "evolutions": [{"variant": "level_up", "result": "b", "requirements": [{"variant": "level", "minLevel": 16}]},
                                                {"variant": "level_up", "result": "d", "requirements": [{"variant": "held_item"}]}]},
    "b": {"preEvolution": "a", "evolutions": [{"variant": "trade", "result": "c", "requirements": []}]},
    "c": {"preEvolution": "b", "evolutions": []},
    "d": {"preEvolution": "a", "evolutions": []},
    "m": {"preEvolution": None, "evolutions": [], "labels": ["legendary"]},
}
MIN_TIER = {"trade": 7, "other": 6}


def test_evolution_rules_by_tier_and_level():
    # Removing it lets an item or trade evolution, or an under-levelled stage, onto an early ground.
    band = [33, 43]                         # midpoint 38
    assert A.legal(SPECIES, "a", 1, [4, 14], 10, 14, MIN_TIER) == []
    assert A.legal(SPECIES, "a", 1, [4, 14], 10, 21, MIN_TIER)       # past 16 + 4
    assert A.legal(SPECIES, "b", 3, [18, 28], 15, 20, MIN_TIER)       # under its evolution level 16
    assert A.legal(SPECIES, "d", 5, band, 40, 42, MIN_TIER)           # item evolution before tier 6
    assert A.legal(SPECIES, "d", 6, band, 40, 42, MIN_TIER) == []
    assert A.legal(SPECIES, "d", 6, band, 36, 42, MIN_TIER)           # under the band's upper half
    assert A.legal(SPECIES, "c", 6, band, 40, 42, MIN_TIER)           # trade evolution before tier 7
    assert A.legal(SPECIES, "m", 8, band, 40, 42, MIN_TIER)           # legendary
    assert A.legal(SPECIES, "zz", 8, band, 40, 42, MIN_TIER)          # not a species


def test_sign_parser_reads_position_rotation_text_and_forceload():
    # Removing it lets the sign checks run on nothing and pass vacuously.
    lines = ["forceload add 17 33",
             "setblock 17 70 33 minecraft:oak_sign[rotation=5]{front_text:{messages:['\"A\"','\"It\\'s\"','\"\"','\"\"']}} replace",
             "setblock 99 70 99 minecraft:oak_sign[rotation=0]{front_text:{messages:['\"B\"']}} replace"]
    s = A.parse_signs(lines)
    assert s[0] == (17, 70, 33, "minecraft:oak_sign", 5, ["A", "It's", "", ""], True)
    assert s[1][6] is False


# ------------------------------------------------------------------------------------------------- the real records
@pytest.fixture(scope="module")
def inp():
    try:
        i = A.Inputs()
    except Exception as exc:  # the heightmap is outside the repo
        pytest.skip("NOT_EXECUTED: inputs unavailable: %s" % exc)
    if i.species is None:
        pytest.skip("NOT_EXECUTED: no Cobblemon 1.8 jar (COBBLERS_JAR_DIR)")
    if i.features is None or not i.paint_dir.is_dir():
        pytest.skip("NOT_EXECUTED: derived/towns or build/paint absent")
    return i


def _real():
    return A.jload(A.TG), A.jload(A.HABITATS), A.jload(A.SPAWNS)


def _fails(R):
    return {(r["subject"], r["check"]) for r in R.rows if r["status"] in ("FAIL", "NOT_EXECUTED")}


def test_real_grounds_fail_only_the_known_defects(inp):
    # Removing it lets a ground over its cap, on a path, in water or overlapping a nest reach the server unseen.
    d, hd, sd = _real()
    if not A.SIGNS.is_file():
        pytest.skip("NOT_EXECUTED: build/datapacks/cobblers_training_grounds not built")
    R = A.audit(d, hd, sd, A.compile_pools_in_memory(sd), A.load_sign_lines(A.SIGNS), inp)
    assert _fails(R) == KNOWN_FAILS, [r for r in R.rows if r["status"] != "PASS" and r["status"] != "NOTE"]
    assert R.count("PASS") >= 8 * 15


# ------------------------------------------------------------------------------ independence: mutate the generator
@pytest.fixture()
def gen(monkeypatch):
    import training_grounds as TG
    before = DATA.read_bytes()
    yield TG
    assert DATA.read_bytes() == before, "the mutation test touched data/training_grounds.json"


def _run_generator(TG, inp, doc=None):
    doc = doc or TG.load()
    hd, sd = TG.merged(doc)
    return A.audit(doc, hd, sd, A.compile_pools_in_memory(sd), TG.sign_lines(doc, inp.g), inp)


def test_control_unmutated_generator_passes(gen, inp):
    # Removing it leaves the mutation tests unable to say the mutation, not the setup, made the audit fail.
    assert _fails(_run_generator(gen, inp)) == KNOWN_FAILS


def test_mutated_band_two_over_fails_the_cap_check(gen, inp, monkeypatch):
    # Removing it loses the proof that the level check does not share the generator's derivation.
    orig = gen.band
    monkeypatch.setattr(gen, "band", lambda doc, cap: tuple(v + 2 for v in orig(doc, cap)))
    R = _run_generator(gen, inp)
    over = {s for s, c in _fails(R) if c == "levels_never_exceed_cap"}
    assert over == {g["id"] for g in gen.load()["grounds"]}
    assert {s for s, c in _fails(R) if c == "pool_matches_record"} == over


def test_mutated_sign_rotation_fails_the_facing_check(gen, inp, monkeypatch):
    # Removing it loses the proof that the facing check is not the generator's own atan2 read back.
    orig = gen.sign_rotation
    monkeypatch.setattr(gen, "sign_rotation", lambda dx, dz: (orig(dx, dz) + 8) % 16)
    R = _run_generator(gen, inp)
    assert {s for s, c in _fails(R) if c == "sign_faces_town"} == {g["id"] for g in gen.load()["grounds"]}


def test_mutated_path_loader_moves_a_ground_onto_a_path_and_fails(gen, inp, monkeypatch):
    # Removing it loses the proof that the path check reads data/route_paths.json itself, not the generator's view.
    real_paths = np.concatenate(list(inp.paths.values()))
    monkeypatch.setattr(gen, "path_points", lambda: np.array([[-1e6, -1e6]]))
    try:
        site = gen.Site(gen.load(), inp.g)
    except Exception as exc:  # kits, the COBBLEVERSE pack or the vanilla jar missing
        pytest.skip("NOT_EXECUTED: the generator's Site cannot load: %s" % exc)
    doc = copy.deepcopy(gen.load())
    gr = next(g for g in doc["grounds"] if g["gym"] == 6)
    gr["site"] = site.choose(gr)
    # the mutation must actually move the ground near a path, measured here, or the test proves nothing
    assert float(np.min(np.hypot(real_paths[:, 0] - gr["site"]["x"], real_paths[:, 1] - gr["site"]["z"]))) < doc["rules"]["path_clear_blocks"]
    R = _run_generator(gen, inp, doc)
    assert ("training_ground_gym6", "path_clearance") in _fails(R)
