"""tools/town_audit.py and the re-application audit fail closed.

Codex review, 2026-09-21: four towns (Erika's, the Merian hut, the Tableland stop, the Rift dig camp) were declared
clean while their paving check said "not checkable"; reapply's audit ignored town_audit's exit code; a place with no
plan, or one the audit could not read, was skipped rather than failed. These fixtures reproduce each and stay.
"""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reapply  # noqa: E402
import town_audit as TA  # noqa: E402

PLAN = {"streets": {"main": {"surface": "minecraft:cobblestone", "cells": [[0, 64, 0, 9]]}},
        "plaza": None, "anchors": [], "lamps": []}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(TA, "ROOT", tmp_path)
    fdir = tmp_path / "build" / "datapacks" / "cobblers_towns" / "data" / "cobblers" / "function" / "towns"
    fdir.mkdir(parents=True)
    (tmp_path / "build" / "town_prep").mkdir(parents=True)
    (tmp_path / "derived" / "towns").mkdir(parents=True)
    return tmp_path, fdir


def _write(repo, prep, town):
    root, fdir = repo
    (root / "build" / "town_prep" / "prep_t.mcfunction").write_text("\n".join(prep))
    (fdir / "t.mcfunction").write_text("\n".join(town))


def test_paving_inside_the_plan_is_clean(repo):
    _write(repo, ["fill 0 64 0 9 64 0 minecraft:cobblestone"], [])
    stray, why = TA.stray_paving_writes("t", PLAN, {"placements": []})
    assert why is None and stray == []


def test_paving_one_column_past_the_plan_is_found(repo):
    # the square brush that ran past a street's cells: one column off the plan is a finding, whatever the landscape
    _write(repo, [], ["fill 0 61 0 10 67 0 minecraft:cobblestone replace minecraft:grass_block"])
    stray, why = TA.stray_paving_writes("t", PLAN, {"placements": []})
    assert why is None and len(stray) == 1


def test_missing_functions_cannot_pass(repo):
    stray, why = TA.stray_paving_writes("t", PLAN, {"placements": []})
    assert why and "missing" in why


def test_a_plan_that_paves_nothing_cannot_pass(repo):
    _write(repo, [], [])
    stray, why = TA.stray_paving_writes("t", {"streets": {}}, {"placements": []})
    assert why


def test_a_place_with_no_plan_fails(repo):
    res = TA.plan_audit("t", str(repo[0]))
    assert res["problems"]


def test_every_recorded_building_is_expected():
    doc = {"placements": [{"id": "a", "settlement": "t", "file": "x.nbt"}, {"id": "b", "settlement": "t", "kind": "earthwork"},
                          {"id": "c", "settlement": "t", "pack_template": "p:q"}, {"id": "v", "settlement": "t",
                                                                                    "kind": "vendor", "pack_template": "p:v"},
                          {"id": "o", "settlement": "other", "file": "y.nbt"}]}
    assert TA.expected_building_ids("t", doc) == {"a", "b", "c"}


def test_not_checkable_makes_town_audit_exit_non_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(TA, "audit", lambda *a, **k: {"unsubstituted": {}, "not_in_policy": {}, "blocks_read": 1,
                                                      "bounds": [0, 0, 0, 0], "y_range": [0, 1], "whitelisted_present": {},
                                                      "in_the_ground_around_it": {}})
    monkeypatch.setattr(TA, "plan_audit", lambda *a, **k: {"roads": {}, "lamps": {"lit": 0, "spots": 0, "block": None},
                                                           "buildings": [], "problems": [],
                                                           "not_checkable": ["paving: could not run"]})
    assert TA.main(["gym4_town", "--world", str(tmp_path)]) == 1


def test_a_place_the_audit_cannot_read_makes_it_exit_non_zero(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise SystemExit("unreadable")
    monkeypatch.setattr(TA, "audit", boom)
    assert TA.main(["gym4_town", "--world", str(tmp_path)]) == 1


def _fake_run(town_stdout, town_exit=0):
    def run(cmd, **k):
        tool = Path(cmd[1]).name
        if tool == "town_audit.py":
            return SimpleNamespace(returncode=town_exit, stdout=town_stdout, stderr="")
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")
    return run


@pytest.mark.parametrize("stdout,exit_code", [
    ("   plan clean: every road cell\n   NOT CHECKABLE  paving\n", 0),       # clean, but something not checked
    ("   plan clean: every road cell\n", 1),                                # says clean, exits non-zero
    ("gym4_town NOT AUDITED: unreadable\n", 1),
])
def test_reapply_audit_does_not_call_a_place_clean_unless_it_is(monkeypatch, tmp_path, stdout, exit_code):
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout, exit_code))
    monkeypatch.setattr(reapply, "OUT", tmp_path)
    monkeypatch.setattr(reapply, "places", lambda *a: ["gym4_town"])
    a = SimpleNamespace(world=str(tmp_path), server_dir=str(tmp_path), source_root=None)
    assert reapply.audit(a) == 1


def test_reapply_audit_with_no_places_is_not_clean(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", _fake_run("   plan clean\n"))
    monkeypatch.setattr(reapply, "OUT", tmp_path)
    monkeypatch.setattr(reapply, "places", lambda *a: [])
    assert reapply.audit(SimpleNamespace(world=str(tmp_path), server_dir=str(tmp_path), source_root=None)) == 1


def test_reapply_audit_passes_a_clean_place(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", _fake_run("   plan clean: every road cell\n"))
    monkeypatch.setattr(reapply, "OUT", tmp_path)
    monkeypatch.setattr(reapply, "places", lambda *a: ["gym4_town"])
    assert reapply.audit(SimpleNamespace(world=str(tmp_path), server_dir=str(tmp_path), source_root=None)) == 0
