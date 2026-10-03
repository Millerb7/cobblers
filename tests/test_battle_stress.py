"""Structural contracts for the deterministic gym stress sampler.

These checks exercise sampling and report construction only.  They do not prove
that Cobblemon executes any sampled party or battle result at runtime.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_stress as ST  # noqa: E402


class _SpeciesName:
    """Minimal evolved-form stand-in: these fixtures intentionally have no evolutions."""

    def __init__(self, _species, name, _level, _moves, _chart):
        self.name = name


def _row(species, pool, *, kind="route", off_corridor=0):
    return {
        "species": species,
        "pool": pool,
        "kind": kind,
        "off_corridor": off_corridor,
        "bucket": "common",
        "lo": 5,
        "hi": 12,
    }


@pytest.fixture
def sampler(monkeypatch):
    """Keep selection focused on availability metadata rather than jar species data."""
    monkeypatch.setattr(ST.B, "Mon", _SpeciesName)
    monkeypatch.setattr(
        ST,
        "answer_scores",
        lambda rows, *_args: {row["species"]: 1 for row in rows},
    )
    return {
        "species": {},
        "moves": {},
        "chart": {},
        "trainer": {"team": [{"species": "foe", "level": 20}]},
    }


def _traditional_starters():
    """The 27 the sampler's 108 = 27 x 4 design was built on. They left starters.json on 2026-10-02/03 (the screen now
    offers the five mythical lines, docs/mechanics/NATIVE_STARTERS_COST.md sections 6a/7) and live in
    data/mythical_starters.json `wild_traditional_starters`; these tests exercise the allocation over that list."""
    doc = json.loads((ROOT / "data" / "mythical_starters.json").read_text(encoding="utf-8"))
    return [ST.B.key(name) for names in doc["wild_traditional_starters"]["regions"].values() for name in names]


def _profiles(sampler):
    starters = _traditional_starters()
    rows = [_row("catch_%d" % number, "route_%d" % number) for number in range(1, 8)]
    return ST.build_profiles(starters, rows, sampler["species"], sampler["moves"], sampler["chart"])


# Without it a changed constant or label allocation can quietly turn the claimed 108-profile stratified sample into
# a differently weighted sample, even though every individual simulated battle still completes.
def test_sample_has_the_declared_total_archetype_distribution_and_starter_representation(sampler):
    profiles = _profiles(sampler)

    assert ST.SAMPLE_SIZE == 108
    assert ST.ARCHETYPE_COUNTS == {
        "collector": 24,
        "loyal_six": 18,
        "favourite_heavy": 18,
        "type_blind": 18,
        "critical_path_only": 15,
        "nuzlocke": 15,
    }
    assert len(profiles) == ST.SAMPLE_SIZE == sum(ST.ARCHETYPE_COUNTS.values())
    assert Counter(profile.archetype for profile in profiles) == ST.ARCHETYPE_COUNTS

    starters = _traditional_starters()
    assert len(starters) == 27
    assert Counter(profile.starter for profile in profiles) == {starter: 4 for starter in starters}


# Without it the stress report would keep seating 27 starters the screen no longer offers and nobody would notice: the
# real offer is the five mythical lines (NATIVE_STARTERS_COST.md section 5 lists this exact break: 108 % 5 = 3 at
# tools/battle_stress.py:92-93, and run()'s `== 27` at :329-331). Strict, so it fails the day the model is fixed.
@pytest.mark.xfail(strict=True, raises=ST.B.SimError,
                   reason="battle_stress models 27 starters x 4; the screen offers 5 (NATIVE_STARTERS_COST.md s5)")
def test_the_stress_sample_seats_the_starters_the_screen_offers(sampler):
    offered = ST.B.config_starters()
    profiles = ST.build_profiles(offered, [], sampler["species"], sampler["moves"], sampler["chart"])
    assert {profile.starter for profile in profiles} == set(offered)


# Without it a critical-path party can collapse to its starter or acquire optional encounters, losing the route-only
# provenance that makes this archetype a useful lower-bound sample.
def test_critical_path_party_contains_route_only_catches_from_the_available_pools(sampler):
    rows = [
        _row("route_one", "road"),
        _row("route_two", "grove"),
        _row("route_three", "cave"),
        _row("route_four", "bridge"),
        _row("route_five", "cliffs"),
        _row("optional", "lake", kind="optional", off_corridor=1),
    ]
    profile = ST.Profile(1, "starter", "critical_path_only", ST.SEED)

    team = ST.select_team(profile, 1, rows, sampler["trainer"], 20, sampler["species"], sampler["moves"], sampler["chart"])

    caught = [member for member in team if member["species"] != profile.starter]
    route_by_species = {row["species"]: row for row in rows if row["kind"] == "route" and not row["off_corridor"]}
    assert len(caught) == 5
    assert {member["species"] for member in caught} == set(route_by_species)
    assert {member["pool"] for member in caught} == {row["pool"] for row in route_by_species.values()}


# Without it Nuzlocke sampling can draw repeatedly from one pool, erasing the one-catch-per-area provenance and
# making an early party look more like a general weighted sample.
def test_nuzlocke_party_takes_one_catch_from_each_available_pool(sampler):
    rows = [
        _row("road_a", "road"),
        _row("road_b", "road"),
        _row("grove_a", "grove"),
        _row("grove_b", "grove"),
        _row("cave_a", "cave"),
        _row("cave_b", "cave"),
    ]
    profile = ST.Profile(1, "starter", "nuzlocke", ST.SEED)

    team = ST.select_team(profile, 1, rows, sampler["trainer"], 20, sampler["species"], sampler["moves"], sampler["chart"])

    caught = [member for member in team if member["species"] != profile.starter]
    assert len(caught) == 3
    assert {member["pool"] for member in caught} == {"road", "grove", "cave"}
    assert len({member["pool"] for member in caught}) == len(caught)


# Without it a mode comparison can sample two different players, so a reported Normal/Challenge difference no
# longer isolates the leader roster change.
def test_each_mode_uses_the_exact_same_sampled_party_for_a_profile_and_gym(monkeypatch, tmp_path):
    sidecar = tmp_path / "availability.json"
    sidecar.write_text(json.dumps({"gyms": {"1": [_row("catch", "road")]}, "caps": {"1": 20}}), encoding="utf-8")
    normal = {"team": [{"species": "normal_foe", "level": 20}]}
    challenge = {"team": [{"species": "challenge_foe", "level": 20}]}
    profile = ST.Profile(1, "starter", "collector", ST.SEED)
    generated = []

    def select(*_args, **_kwargs):
        generated.append(len(generated) + 1)
        return [{"species": "catch_%d" % generated[-1], "level": 18, "pool": "road"}]

    monkeypatch.setattr(ST.B, "find_jar", lambda: "unused.jar")
    monkeypatch.setattr(ST.B, "load_pack", lambda _jar: ({}, {}, {}))
    monkeypatch.setattr(ST.B, "Mon", _SpeciesName)
    monkeypatch.setattr(ST.B, "AVAIL_JSON", sidecar)
    monkeypatch.setattr(ST.B, "gym_leaders", lambda: ({1: {"modes": {"normal": normal, "challenge": challenge}}}, {}))
    monkeypatch.setattr(ST.B, "config_starters", lambda: ["starter_%d" % number for number in range(27)])
    monkeypatch.setattr(ST, "build_profiles", lambda *_args: [profile])
    monkeypatch.setattr(ST, "answer_scores", lambda *_args: {})
    monkeypatch.setattr(ST, "select_team", select)
    monkeypatch.setattr(ST, "fight", lambda *_args, **_kwargs: {"won": True, "faints": 0, "downed": 0, "left": 1.0})
    monkeypatch.setattr(ST, "sampled_order_wins", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(ST, "range", lambda start, stop: [1], raising=False)

    result = ST.run()

    normal_team = result["gyms"]["1"]["normal"]["runs"][0]["team"]
    challenge_team = result["gyms"]["1"]["challenge"]["runs"][0]["team"]
    assert normal_team == challenge_team == [{"species": "catch_1", "level": 18, "pool": "road"}]


# Without it the cap diagnosis can leave a lower-level member unchanged, misclassifying a composition failure as a
# level failure because the supposed cap team never actually reaches the gym's ace cap.
def test_at_cap_fight_raises_every_member_to_the_actual_gym_ace_cap(monkeypatch):
    trainers = json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))["trainers"]
    brock = next(trainer for trainer in trainers if trainer["id"] == "gym_01_brock")
    trainer = ST.mode_trainer(brock, "normal")
    seen_levels = []

    class RecordedMon:
        def __init__(self, _species, _name, level, _moves, _chart):
            self.name = _name
            seen_levels.append(level)

    monkeypatch.setattr(ST.B, "Mon", RecordedMon)
    monkeypatch.setattr(ST.B, "build_leader", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ST.B, "run_gauntlet", lambda *_args, **_kwargs: (True, 0, 0, 1.0))
    specs = [
        {"species": "starter", "level": 5, "pool": "oak"},
        {"species": "catch", "level": 17, "pool": "road"},
        {"species": "late_catch", "level": 19, "pool": "cave"},
    ]

    ST.fight(specs, trainer, {}, {}, {}, at_cap=True)

    ace_cap = max(member["level"] for member in trainer["team"])
    assert seen_levels == [ace_cap] * len(specs)


# Without it a hidden source of randomness can make the same seed produce a different profile or party on a later
# report run, making Normal/Challenge summaries impossible to reproduce or compare.
def test_profile_and_team_generation_are_reproducible_from_the_fixed_seed(sampler):
    first_profiles = _profiles(sampler)
    second_profiles = _profiles(sampler)
    rows = [_row("catch_%d" % number, "route_%d" % number) for number in range(1, 8)]

    first_teams = {
        profile.id: ST.select_team(profile, 3, rows, sampler["trainer"], 30, sampler["species"], sampler["moves"], sampler["chart"])
        for profile in first_profiles
    }
    second_teams = {
        profile.id: ST.select_team(profile, 3, rows, sampler["trainer"], 30, sampler["species"], sampler["moves"], sampler["chart"])
        for profile in second_profiles
    }

    assert first_profiles == second_profiles
    assert first_teams == second_teams
