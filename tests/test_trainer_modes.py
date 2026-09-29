"""Normal/Challenge trainer-mode contracts against the generated active data.

These tests validate generated source data and the non-writing active freshness check.
They do not prove RCT reads the variants or that mode selection behaves in Minecraft.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TRAINERS_DOC = json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "docs" / "story" / "TRAINER_RULES.json").read_text(encoding="utf-8"))

ACTIVE_GYMS = sorted(
    (
        trainer
        for trainer in TRAINERS_DOC["trainers"]
        if trainer.get("class") == "gym_leader"
        and trainer.get("status") == "authored"
        and 1 <= trainer.get("order", 0) <= 8
    ),
    key=lambda trainer: trainer["order"],
)
ACTIVE_ROUTES = sorted(
    (
        trainer
        for trainer in TRAINERS_DOC["trainers"]
        if trainer.get("class") in {"route", "optional_route"}
        and 1 <= trainer.get("route_order", 0) <= 8
    ),
    key=lambda trainer: (trainer["route_order"], trainer["trainer_order"]),
)
ACTIVE_TRAINERS = ACTIVE_GYMS + ACTIVE_ROUTES


def _ceiling(team):
    return max(member["level"] for member in team)


# Without it an active gym or Route 1-8 trainer can silently lose a variant, leaving the server-wide choice incomplete.
def test_every_active_gym_and_route_1_to_8_has_exactly_normal_and_challenge_modes():
    assert [trainer["order"] for trainer in ACTIVE_GYMS] == list(range(1, 9))
    assert {trainer["route_order"] for trainer in ACTIVE_ROUTES} == set(range(1, 9))
    assert ACTIVE_TRAINERS
    for trainer in ACTIVE_TRAINERS:
        assert set(trainer.get("modes", {})) == {"normal", "challenge"}, trainer["id"]


# Without it existing placement tooling can receive a payload that no longer means Normal mode.
def test_active_trainers_top_level_team_and_rct_exactly_mirror_normal_mode():
    for trainer in ACTIVE_TRAINERS:
        normal = trainer["modes"]["normal"]
        assert trainer["team"] == normal["team"], trainer["id"]
        assert trainer["rct"] == normal["rct"], trainer["id"]


# Without it a mode can shift the configured gym ace curve and turn difficulty into level inflation.
def test_gym_modes_preserve_the_configured_ace_ceilings():
    expected = RULES["difficulty"]["gym_ace_levels"]
    assert [trainer["ace_level"] for trainer in ACTIVE_GYMS] == expected
    for trainer, ceiling in zip(ACTIVE_GYMS, expected):
        assert _ceiling(trainer["modes"]["normal"]["team"]) == ceiling, trainer["id"]
        assert _ceiling(trainer["modes"]["challenge"]["team"]) == ceiling, trainer["id"]


# Without it the defining Full-Team rule can regress while every mode and cap check still passes.
def test_every_challenge_gym_has_six_members_and_a_six_member_answer_line():
    for trainer in ACTIVE_GYMS:
        challenge = trainer["modes"]["challenge"]
        assert len(challenge["team"]) == 6, trainer["id"]
        assert len(challenge["open_line"]) == 6, trainer["id"]
        assert len(set(challenge["open_line"])) == 6, trainer["id"]


# Without it Challenge can exceed Normal's cap, making a roster change into undisclosed level inflation.
def test_challenge_never_exceeds_the_normal_level_cap_for_an_active_trainer():
    for trainer in ACTIVE_TRAINERS:
        normal_cap = _ceiling(trainer["modes"]["normal"]["team"])
        challenge_cap = _ceiling(trainer["modes"]["challenge"]["team"])
        assert challenge_cap <= normal_cap, trainer["id"]


# Without it Challenge can add route encounters or turn a short teaching fight into an unbounded party.
def test_route_challenge_preserves_density_and_adds_at_most_one_member():
    for order in range(1, 9):
        trainers = [trainer for trainer in ACTIVE_ROUTES if trainer["route_order"] == order]
        assert len(trainers) == RULES["routes"][order - 1]["expected_count"]
        assert len(trainers) == len({trainer["id"] for trainer in trainers})
        for trainer in trainers:
            normal_size = len(trainer["modes"]["normal"]["team"])
            challenge_size = len(trainer["modes"]["challenge"]["team"])
            assert challenge_size <= normal_size + 1, trainer["id"]


# Without it a route loses its teaching identity or the two modes collapse into the same stated intent.
def test_every_route_has_a_nonempty_theme_and_distinct_mode_intent():
    for order in range(1, 9):
        trainers = [trainer for trainer in ACTIVE_ROUTES if trainer["route_order"] == order]
        assert trainers
        for trainer in trainers:
            assert isinstance(trainer.get("route_theme"), str) and trainer["route_theme"].strip(), trainer["id"]
            intent = trainer.get("mode_intent")
            assert set(intent or {}) == {"normal", "challenge"}, trainer["id"]
            assert all(isinstance(value, str) and value.strip() for value in intent.values()), trainer["id"]
            assert intent["normal"] != intent["challenge"], trainer["id"]


# Without it the final gym can regress to an unproven doubles fight, a lower cap, or the banned Mewtwo roster.
def test_giovanni_is_a_level_55_singles_fight_without_mewtwo_in_either_mode():
    giovanni = next(trainer for trainer in TRAINERS_DOC["trainers"] if trainer["id"] == "gym_08_giovanni")
    assert giovanni["status"] == "authored"
    assert giovanni["ace_level"] == 55
    for mode in ("normal", "challenge"):
        variant = giovanni["modes"][mode]
        assert variant["rct"]["battleFormat"] == "GEN_9_SINGLES"
        assert _ceiling(variant["team"]) == 55
        assert {member["species"] for member in variant["team"]}.isdisjoint({"mewtwo"})


# Without it regeneration can silently revive the retired surface pins or drop one cave examination.
def test_check_active_succeeds_and_generates_the_ten_victory_road_cave_fights():
    result = subprocess.run(
        [sys.executable, "docs/story/generate_trainers.py", "--check-active"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Victory Road uses ten cave stands" in result.stdout
    assert TRAINERS_DOC["generation_contract"]["preserved_blocked_route_orders"] == []
    victory_road = [trainer for trainer in TRAINERS_DOC["trainers"] if trainer.get("route_order") == 9]
    assert [trainer["id"] for trainer in victory_road] == [
        f"route_09_trainer_{index:02d}" for index in range(1, 11)
    ]
    assert all(set(trainer["modes"]) == {"normal", "challenge"} for trainer in victory_road)
    assert all(trainer["placement"]["placement_authority"].endswith("trainer stand") for trainer in victory_road)
