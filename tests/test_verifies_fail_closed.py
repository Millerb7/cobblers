"""The sweep after the Codex review of 2026-09-21: every other verify with the same fail-open shape, fixed and held.

Each fixture gives a verify nothing to check (or a world missing what the plan builds) and requires it to fail:
  light_plan check    "0 positions, 0 dark" passed a place the world did not hold (Surge's town, 2026-09-21); the
                      audit also asked it about the dark-by-design ruins, so it could never have come back clean
  signposts verify    "0 of 0 posts standing" with an empty report
  traders verify      "0 traders checked, 0 problems" for a selection matching nothing
  habitat verify      "0 placed blocks checked, 0 problems"
  place_town verify   a building the data records but the placement report does not list was never verified
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import light_plan as LP  # noqa: E402


class BlankWorld:
    def __init__(self, *a):
        pass

    def block(self, x, y, z):
        return "minecraft:air"


def _room_model():
    m = LP.Model((0, 0, 6, 6), 0, 6)
    for x in range(7):
        for z in range(7):
            m.set(x, 0, z, "minecraft:stone")
            m.set(x, 4, z, "minecraft:stone")
    return m


def _check(monkeypatch, tmp_path, model, scope, settlements=("t",), doc=None):
    import build_audit
    doc = doc or {"settlements": {"t": {"plan": {}}}, "placements": []}
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "placements.json").write_text(json.dumps(doc))
    monkeypatch.setattr(LP, "ROOT", tmp_path)
    monkeypatch.setattr(LP, "build_model", lambda *a, **k: (model, scope, {}, None))
    monkeypatch.setattr(build_audit, "World", BlankWorld)
    monkeypatch.setattr(LP, "world_light", lambda *a: 15)
    return LP.cmd_check(SimpleNamespace(world=str(tmp_path / "w"), settlements=list(settlements), source_root=None,
                                        server_dir=None, dump=None))


def test_light_check_fails_when_the_world_lacks_what_the_plan_builds(monkeypatch, tmp_path):
    m = _room_model()
    scope = np.ones_like(m.opaque)                     # the model has roofed positions; the blank world has none
    scope[0, 0, 0] = False                             # (a scope of every cell is how the check knows the cavern)
    assert _check(monkeypatch, tmp_path, m, scope) == 1


def test_light_check_fails_when_the_plan_has_nothing_to_check(monkeypatch, tmp_path):
    m = _room_model()
    assert _check(monkeypatch, tmp_path, m, np.zeros_like(m.opaque)) == 1


def test_light_check_refuses_a_place_dark_by_design(monkeypatch, tmp_path):
    m = _room_model()
    doc = {"settlements": {"t": {"plan": {"lighting": {"dark_by_design": "a ruin"}}}}, "placements": []}
    assert _check(monkeypatch, tmp_path, m, np.ones_like(m.opaque), doc=doc) == 1


def test_the_audit_leaves_out_exactly_the_places_dark_by_design():
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    places = LP.light_places(doc)
    assert "the_scar" not in places and "jungle_ruins" not in places
    assert "hometown" in places and "displaced_city" in places


def test_signposts_verify_with_no_posts_fails(monkeypatch, tmp_path):
    import signposts
    rep = tmp_path / "signposts.json"
    rep.write_text(json.dumps({"wood": "spruce", "posts": []}))
    monkeypatch.setattr(signposts, "REPORT", rep)
    assert signposts.verify(SimpleNamespace(world=str(tmp_path))) == 1


def test_signposts_verify_with_nonempty_truncated_report_fails(monkeypatch, tmp_path):
    import signposts
    rep = tmp_path / "signposts.json"
    rep.write_text(json.dumps({"wood": "spruce", "posts": [{"id": "route_1_leaving_home"}]}))
    monkeypatch.setattr(signposts, "REPORT", rep)
    monkeypatch.setattr(signposts, "expected_post_ids",
                        lambda: {"route_1_leaving_home", "route_1_leaving_gym1"})
    assert signposts.verify(SimpleNamespace(world=str(tmp_path))) == 1


def test_traders_verify_that_checks_no_trader_fails(monkeypatch, tmp_path):
    import traders
    monkeypatch.setattr(traders, "static_problems", lambda *a, **k: [])
    monkeypatch.setattr(traders, "world_counts", lambda *a, **k: {})
    man = tmp_path / "traders.json"
    man.write_text(json.dumps({"traders": []}))
    assert traders.main(["--manifest", str(man), "verify", "--world", str(tmp_path)]) == 1


def test_habitat_verify_with_nothing_placed_fails(monkeypatch, tmp_path):
    import habitat_blocks as HB
    monkeypatch.setattr(HB, "static_problems", lambda *a, **k: [])
    monkeypatch.setattr(HB, "world_problems", lambda *a, **k: [])
    man, sp = tmp_path / "hb.json", tmp_path / "spawns.json"
    man.write_text(json.dumps({"blocks": []}))
    sp.write_text("{}")
    assert HB.main(["--manifest", str(man), "--spawns", str(sp), "verify", "--world", str(tmp_path)]) == 1


def test_floor_verify_names_a_building_the_report_left_out(monkeypatch, tmp_path):
    import place_town as PT
    import runtime_guard
    (tmp_path / "derived" / "towns").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "derived" / "towns" / "t_placement.json").write_text(json.dumps({"buildings": []}))
    (tmp_path / "data" / "placements.json").write_text(json.dumps(
        {"placements": [{"id": "house_1", "settlement": "t", "file": "kits/x.nbt"}]}))
    monkeypatch.setattr(PT, "ROOT", tmp_path)
    monkeypatch.setattr(runtime_guard, "rcon", lambda d: (SimpleNamespace(run=lambda cmds, pw, **k: []), "pw"))
    res = PT.verify("t", str(tmp_path))
    assert res["unverified"] and "house_1" in res["unverified"][0]
