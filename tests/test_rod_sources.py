"""tools/rod_sources.py and tools/fishermen.py: the rods fishermen hand out, and the check that counts them.

Written by the session that built the fishermen (no separate test author was available); the mutation tests below change
the CODE UNDER TEST's inputs (the NPC chain the check reads), never data/fishermen.json's expectation, so the check is
shown to bite.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fishermen  # noqa: E402
import rod_sources as RS  # noqa: E402


def test_the_campaign_hands_out_at_least_the_declared_number_of_rods_through_npcs():
    # Removing this lets the fishermen be deleted, or their chain broken, with nothing saying the rods are gone again.
    g = RS.gather()
    assert g["problems"] == [], g["problems"]


def test_every_fisherman_in_the_table_resolves_to_a_seated_npc_with_its_badge_gate():
    tb = fishermen.table()
    npcs = {n["npc"]: n for n in RS.gather()["npcs"]}
    for f in tb["fishermen"]:
        n = npcs[f["id"]]
        assert n["rod"] == "cobblemon:" + f["rod"]
        assert n["gates"] == [f["gate"]["flag"]], "the give transition must require the badge flag itself"
        assert n["entry_gate"] == [f["gate"]["flag"]], "the conversation must turn a player below the gate away"
        assert "npc_seats.json" in n["placed_by"]


def test_dropping_a_fishermans_quest_breaks_the_floor(monkeypatch):
    # Removing this leaves the floor unproven: a check that never fails when a rod stops being handed out.
    real = RS.npc_sources
    monkeypatch.setattr(RS, "npc_sources", lambda rods: [n for n in real(rods) if n["npc"] != "npc_fisher_viltri"])
    probs = RS.gather()["problems"]
    assert any("great_rod" in p or "npc_fisher_viltri" in p or "distinct rods" in p for p in probs), probs


def test_an_ungated_stronger_rod_is_a_problem(monkeypatch):
    # Removing this lets a Dive Rod be handed to a player on the first coast.
    real = RS.npc_sources

    def ungated(rods):
        out = real(rods)
        for n in out:
            if n["rod"] != "cobblemon:poke_rod":
                n["gates"] = []
        return out
    monkeypatch.setattr(RS, "npc_sources", ungated)
    probs = RS.gather()["problems"]
    assert sum("badge flag" in p for p in probs) >= 5, probs


def test_a_rod_id_outside_the_universe_is_a_problem(monkeypatch):
    # Removing this lets a typo (cobblemon:grate_rod) in a reward pass for a rod nobody can receive.
    monkeypatch.setattr(RS, "universe", lambda: (["cobblemon:poke_rod"], RS.jload("fishermen.json")))
    probs = RS.gather()["problems"]
    assert any("is not a rod Cobblemon 1.8.0 registers" in p for p in probs), probs


def test_the_derived_records_match_the_table():
    # Removing this lets a hand edit of a spliced record stand against the table that owns it.
    assert fishermen.check(fishermen.table()) == []


def test_each_fisherman_stands_on_a_distinct_water_with_a_distinct_rod():
    tb = fishermen.table()
    rods = [f["rod"] for f in tb["fishermen"]]
    waters = [repr(f["water"]) + repr(f["near"]) for f in tb["fishermen"]]
    assert len(set(rods)) == len(rods) == len(set(waters)) >= tb["check"]["min_waters"]
