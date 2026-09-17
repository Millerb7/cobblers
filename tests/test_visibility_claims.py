"""Visibility claims: tools/visibility_claims.py and the visibility check in tools/validate_data.py.

A claim that something can or cannot be seen is measured, not trusted. These tests use a synthetic repository in tmp_path
(a flat heightmap with an optional wall, one route, two towns) with load_terrain patched, so they run without the source
tree. The last tests read the real data/ for structure only (citations and coverage), which needs no terrain.

Not covered: the real heightmap and canopy (the validator run with --source-root does that), sightlines.cast itself
(tests/test_landmark_trees.py), and anything in game.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import validate_data as V  # noqa: E402
import visibility_claims as VC  # noqa: E402

N = 400
TOWER = (300, 200)


def poly(pts):
    out, along = [], 0.0
    for i, (x, z) in enumerate(pts):
        if i:
            along += ((x - pts[i - 1][0]) ** 2 + (z - pts[i - 1][1]) ** 2) ** 0.5
        out.append({"x": x, "y": 100, "z": z, "at_distance_blocks": along, "corridor_width_blocks": 16})
    return out


def repo(tmp_path, wall=False, claims=None, why_here="A tower seen from the road (visibility:tower_from_road).", measured=None):
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    routes = {"schema": "cobblers.routes/1", "routes": [
        {"id": "road", "from_town": "a", "to_town": "b", "corridor": {"polyline": poly([(20, 200), (200, 200)])},
         "water_crossings": [{"start": {"at_distance_blocks": 80}, "end": {"at_distance_blocks": 100}}], "landmarks": []}]}
    towns = {"schema": "cobblers.towns/1", "towns": [
        {"id": "tower", "role": "outpost", "tier": "outpost", "status": "proposed", "centre": {"x": TOWER[0], "z": TOWER[1]},
         "footprint": {"min_x": 295, "max_x": 305, "min_z": 195, "max_z": 205}, "waystone": {"kind": "none"}, "why_here": why_here}]}
    files = {"routes.json": routes, "towns.json": towns,
             "landmarks.json": {"schema": "cobblers.landmarks/1", "landmarks": []},
             "foliage.json": {"schema": "cobblers.foliage/1", "landmark_trees": []},
             "rivers.json": {"schema": "cobblers.rivers/1", "courses": []},
             "world.json": {"schema": "cobblers.world/1", "heightmap": {"sha256": "abc"}}}
    claim = {"id": "tower_from_road", "claim": "The tower is seen from the road.",
             "recorded_in": {"file": "data/towns.json", "record": "tower", "field": "why_here"}, "expect": "visible",
             "observers": {"type": "route", "route_id": "road", "spacing": 10},
             "target": {"type": "town", "id": "tower", "height_above_ground": 8}, "surface": "terrain",
             "measured": measured, "fragile": False}
    files["visibility.json"] = {"schema": "cobblers.visibility/1", "heightmap_sha256": "abc",
                                "canopy": {"path": "build/paint/canopy.npz", "sha256": None},
                                "rules": {"fragile_max_seen": VC.FRAGILE_MAX_SEEN, "fragile_max_share": VC.FRAGILE_MAX_SHARE,
                                          "fragile_min_margin_blocks": VC.FRAGILE_MIN_MARGIN},
                                "claims": claims if claims is not None else [claim]}
    for name, doc in files.items():
        (d / name).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    lib = tmp_path / "kits" / "structures" / "foliage"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "library.json").write_text(json.dumps({"objects": []}), encoding="utf-8")
    heights = np.full((N, N), 100.0, dtype=np.float32)
    if wall:
        heights[:, 250:252] = 200.0          # a wall between the road and the tower
    return d, heights


def run(d, heights, monkeypatch):
    world = json.loads((d / "world.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(V, "load_terrain", lambda ctx: {"heights": heights, "world": world})
    ctx = V.Context(d, None, V.Report())
    V.check_schema(ctx)
    V.check_visibility(ctx)
    return [f.message for f in ctx.report.findings if f.check == "visibility" and f.severity == V.ERROR]


def measured_now(d, heights, claim_index=0):
    doc = json.loads((d / "visibility.json").read_text(encoding="utf-8"))
    inp = VC.Inputs(d, heights, {}, None)
    return VC.measure(doc["claims"][claim_index], inp)


def test_open_ground_measures_every_point_and_a_wall_none(tmp_path):
    d, flat = repo(tmp_path)
    m = measured_now(d, flat)
    assert m == {"seen": 18, "of": 18, "unit": "observer points"}
    d2, walled = repo(tmp_path / "w", wall=True)
    assert measured_now(d2, walled)["seen"] == 0


def test_a_recorded_measurement_that_matches_passes(tmp_path, monkeypatch):
    d, flat = repo(tmp_path, measured={"seen": 18, "of": 18, "unit": "observer points"})
    assert run(d, flat, monkeypatch) == []


# removing the drift comparison lets terrain or foliage change a claim's count silently
def test_drift_fails(tmp_path, monkeypatch):
    d, flat = repo(tmp_path, measured={"seen": 16, "of": 18, "unit": "observer points"})
    errs = run(d, flat, monkeypatch)
    assert any('claim "tower_from_road" drifted' in e for e in errs), errs


# removing holds() lets a claim that is now false pass as long as its record was rewritten to match
def test_a_false_claim_fails_even_when_its_record_matches(tmp_path, monkeypatch):
    d, walled = repo(tmp_path, wall=True, measured={"seen": 0, "of": 18, "unit": "observer points"})
    errs = run(d, walled, monkeypatch)
    assert any('claim "tower_from_road" is false' in e for e in errs), errs


# removing the negative expectation lets a "cannot be seen" claim become visible without anyone noticing
def test_not_visible_claim_fails_when_it_becomes_visible(tmp_path, monkeypatch):
    d, flat = repo(tmp_path, measured={"seen": 18, "of": 18, "unit": "observer points"})
    doc = json.loads((d / "visibility.json").read_text(encoding="utf-8"))
    doc["claims"][0]["expect"] = "not_visible"
    (d / "visibility.json").write_text(json.dumps(doc), encoding="utf-8")
    assert any("is false" in e for e in run(d, flat, monkeypatch))


# removing the citation rule lets a record state a visibility claim the registry never measures
def test_the_stating_record_must_cite_the_claim(tmp_path, monkeypatch):
    d, flat = repo(tmp_path, why_here="A tower seen from the road.", measured={"seen": 18, "of": 18, "unit": "observer points"})
    assert any("does not cite visibility:tower_from_road" in e for e in run(d, flat, monkeypatch))


# removing the fragility rules lets "visible from 2 of N points" pass as plain "visible"
def test_fragile_claims_must_be_flagged_and_said_so(tmp_path, monkeypatch):
    d, flat = repo(tmp_path, measured={"seen": 3, "of": 3, "unit": "observer points"})
    doc = json.loads((d / "visibility.json").read_text(encoding="utf-8"))
    doc["claims"][0]["observers"]["spacing"] = 60          # 3 observer points: fragile by the rule
    (d / "visibility.json").write_text(json.dumps(doc), encoding="utf-8")
    errs = run(d, flat, monkeypatch)
    assert any("fragile is False but the rule gives True" in e for e in errs), errs
    assert any("does not say so" in e for e in errs), errs
    doc["claims"][0]["fragile"] = True
    (d / "visibility.json").write_text(json.dumps(doc), encoding="utf-8")
    towns = json.loads((d / "towns.json").read_text(encoding="utf-8"))
    towns["towns"][0]["why_here"] = "A tower, fragile: seen from 3 points (visibility:tower_from_road)."
    (d / "towns.json").write_text(json.dumps(towns), encoding="utf-8")
    assert run(d, flat, monkeypatch) == []


def test_fragility_rule():
    c = {"expect": "visible"}
    assert VC.is_fragile(c, {"seen": 10, "of": 400})
    assert VC.is_fragile(c, {"seen": 11, "of": 400})          # 2.75% is under 5%
    assert not VC.is_fragile(c, {"seen": 30, "of": 400})
    assert not VC.is_fragile({"expect": "not_visible"}, {"seen": 0, "of": 5})
    assert VC.is_fragile(c, {"margin_blocks": 1.9}) and not VC.is_fragile(c, {"margin_blocks": 4.3})


def test_route_observers_near_water_crossings(tmp_path):
    d, flat = repo(tmp_path)
    inp = VC.Inputs(d, flat, {}, None)
    pts = VC.observers({"type": "route", "route_id": "road", "spacing": 10, "near_water_crossings_blocks": 10}, inp)
    assert [p[0] for p in pts] == [90, 100, 110, 120, 130]      # along 70-110 inclusive: the crossing 80-100 padded by 10


def test_resolve_field_steps_through_lists_by_id():
    rec = {"landmarks": [{"id": "river", "relation": "x"}], "a": {"b": "y"}}
    assert V._resolve_field(rec, "landmarks.river.relation") == "x"
    assert V._resolve_field(rec, "a.b") == "y"
    assert V._resolve_field(rec, "landmarks.lake.relation") is None


# ------------------------------------------------------------- real data (structure only, no terrain)


def _real():
    vis = json.loads((ROOT / "data" / "visibility.json").read_text(encoding="utf-8"))
    fol = json.loads((ROOT / "data" / "foliage.json").read_text(encoding="utf-8"))
    return vis, fol


# removing this lets a landmark tree add a viewpoint leg to data/foliage.json that no claim measures
def test_every_landmark_viewpoint_has_a_claim():
    vis, fol = _real()
    missing = []
    for lt in fol["landmark_trees"]:
        if lt.get("landmark", True) is False:
            assert "seen_from" not in lt
            continue
        mine = [c for c in vis["claims"] if c["target"].get("type") == "landmark_tree" and c["target"]["id"] == lt["id"]]
        for o in lt["seen_from"]:
            for leg in o.get("legs") or []:
                if not any(c["observers"].get("leg") == leg for c in mine):
                    missing.append((lt["id"], leg))
            if o["kind"] == "ring" and not any(c["observers"]["type"] == "ring" for c in mine):
                missing.append((lt["id"], "ring"))
    assert missing == []


# removing this lets a claim point at a record that no longer states it
def test_every_claim_is_cited_where_it_is_recorded():
    vis, _ = _real()
    bad = []
    for c in vis["claims"]:
        rel = c["recorded_in"]["file"]
        text = (ROOT / rel).read_text(encoding="utf-8")
        if rel.endswith(".json"):
            doc = json.loads(text)
            rec = V._records_by_id(doc).get(c["recorded_in"]["record"])
            val = V._resolve_field(rec, c["recorded_in"]["field"]) if rec else None
            if val is None or (isinstance(val, str) and "visibility:%s" % c["id"] not in val):
                bad.append(c["id"])
        elif "visibility:%s" % c["id"] not in text:
            bad.append(c["id"])
    assert bad == []


def test_demoted_weeping_elder_is_not_a_place():
    _, fol = _real()
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    we = next(t for t in fol["landmark_trees"] if t["id"] == "weeping_elder_tilpey")
    assert we["landmark"] is False and "seen_from" not in we and we["demoted"]["why"]
    assert all(t["id"] != "weeping_elder_tilpey" for t in towns)
