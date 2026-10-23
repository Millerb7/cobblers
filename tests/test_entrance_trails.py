"""The trails from the towns to the cave and mine entrances (tools/entrance_trails.py, audited by
tools/entrance_trails_audit.py, table data/entrance_trails.json).

What breaks without these tests: a planner change that lays a trail through water, a building or a cliff; a pack whose
ribbon floats off the heightmap, whose centre line has a gap, whose lanterns or sign are missing or face the wrong way;
a table row naming an entrance that no longer exists. The audit shares no code with the planner (it reads the written
functions and recomputes from the heightmap and data/*.json), so the mutation tests here wrap the GENERATOR's functions
and leave data/ alone: a mutation that edited the record would move the expectation with the output and prove nothing.

NOT COVERED: the walk in a running game, the trees and ponds no data file carries, the audit's check against other built
packs on a real build (a fresh worktree has none; the check itself is exercised on a fixture below).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import entrance_trails as EB  # noqa: E402
import entrance_trails_audit as AU  # noqa: E402

DOC = json.loads((ROOT / "data" / "entrance_trails.json").read_text(encoding="utf-8"))
pytestmark = pytest.mark.skipif(not (ROOT / "data" / "world.json").is_file(), reason="no world config")


@pytest.fixture(scope="module")
def planned():
    try:
        return EB.build_plans()
    except SystemExit as e:           # no heightmap here
        pytest.skip("heightmap unavailable: %s" % e)


def write(tmp_path, plans, g, rules, name="p"):
    pack, guides = tmp_path / name / "t", tmp_path / name / "g"
    EB.write_packs(plans, g, rules, pack, guides, tmp_path / name / "r.json")
    return pack, guides


@pytest.fixture(scope="module")
def good(planned, tmp_path_factory):
    plans, g, rules = planned
    tmp = tmp_path_factory.mktemp("good")
    pack, guides = write(tmp, plans, g, rules)
    return pack, guides


def audit(pack, guides, **kw):
    probs, notes = AU.audit(pack, guide_pack=guides, do_other_packs=False, **kw)
    return probs, notes


# ---------------------------------------------------------------------------- the table


def test_every_trail_names_a_real_entrance_town_or_route_and_a_unique_id():
    ents = EB.entrances()
    towns = EB.towns()
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"]
    rids = {r["id"] for r in routes}
    ids = [t["id"] for t in DOC["trails"]]
    assert len(ids) == len(set(ids)) == 6
    for t in DOC["trails"]:
        assert t["to"] in ents, t["id"]
        assert (t.get("from_town") in towns) != (t.get("from_route") in rids), "%s: exactly one of from_town / from_route" % t["id"]
        assert t["system"] == ents[t["to"]]["system"], t["id"]


def test_every_system_has_a_guide_and_every_guide_a_real_entrance():
    ents = EB.entrances()
    systems = {e["system"] for e in ents.values()}
    assert {g["system"] for g in DOC["guides"]} == systems
    for g in DOC["guides"]:
        assert g["goes_to"] in ents and ents[g["goes_to"]]["system"] == g["system"], g["id"]
        assert g["town"] in EB.towns()


# ---------------------------------------------------------------------------- the built pack


def test_a_built_pack_passes_the_audit_and_walks_every_trail(good):
    probs, notes = audit(*good)
    assert probs == [], probs
    walked = [n for n in notes if n.startswith("trail_")]
    assert len(walked) == 6 and not any("NOT WALKED" in n for n in walked), notes


def test_each_trail_is_short_enough_and_the_sign_names_it(planned):
    plans, g, rules = planned
    assert len(plans) == 6
    for p in plans:
        assert 100 < p["arc"] <= rules["max_length_blocks"], p["spec"]["id"]
        assert abs(p["sign_n"] - p["arc"]) <= 5.0 + 1e-9
        assert p["front"][0] and all(len(t) <= 15 for t in p["front"] + p["back"])


def test_the_audit_is_independent_of_the_planner_module():
    src = (ROOT / "tools" / "entrance_trails_audit.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+entrance_trails\b", src, re.M), \
        "the audit must not import the planner: a shared derivation cannot catch a shared mistake"


# ---------------------------------------------------------------------------- mutate the GENERATOR; the audit must bite


def short_plan():
    plans, g, rules = EB.build_plans(only="trail_hollow_reach_steepside")
    return plans, g, rules


def audit_mutant(tmp_path, plans, g, rules):
    pack, guides = write(tmp_path, plans, g, rules, "m")
    probs, _ = audit(pack, guides)
    # only the trail we built: the other five are absent from this pack
    return [p for p in probs if p.startswith("trail_hollow_reach_steepside:")]


def test_baseline_of_the_short_plan_is_clean(tmp_path):
    plans, g, rules = short_plan()
    assert audit_mutant(tmp_path, plans, g, rules) == []


def test_a_flank_block_outside_the_table_is_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(EB, "flank_block", lambda rules, x, z: "minecraft:stone")
    probs = audit_mutant(tmp_path, *short_plan())
    assert any("outside the table" in p for p in probs), probs


def test_a_ribbon_laid_one_block_off_the_ground_is_caught(tmp_path, monkeypatch):
    real = EB.trail_commands

    def lifted(plan, g, rules):
        return [re.sub(r"^(setblock -?\d+ )(-?\d+)( -?\d+ minecraft:(dirt_path|gravel|coarse_dirt))$",
                       lambda m: m.group(1) + str(int(m.group(2)) + 1) + m.group(3), l) for l in real(plan, g, rules)]
    monkeypatch.setattr(EB, "trail_commands", lifted)
    probs = audit_mutant(tmp_path, *short_plan())
    assert any("heightmap's ground" in p for p in probs), probs


def test_a_sign_facing_away_from_the_traveller_is_caught(tmp_path, monkeypatch):
    real = EB.place_sign
    monkeypatch.setattr(EB, "place_sign", lambda *a, **k: (lambda t: (t[0], t[1], t[2], (t[3] + 8) % 16))(real(*a, **k)))
    probs = audit_mutant(tmp_path, *short_plan())
    assert any("does not face the traveller" in p for p in probs), probs


def test_a_sign_with_the_wrong_distance_is_caught(tmp_path, monkeypatch):
    real = EB.sign_lines
    monkeypatch.setattr(EB, "sign_lines", lambda spec, rules, n, town: real(spec, rules, n + 300.0, town))
    probs = audit_mutant(tmp_path, *short_plan())
    assert any("the sign says" in p for p in probs), probs


def test_a_gap_in_the_centre_line_is_caught(tmp_path, monkeypatch):
    real = EB.ribbon

    def gapped(cells):
        rb = real(cells)
        mid = len(cells) // 2
        for c in cells[mid - 2:mid + 3]:
            rb.pop(c, None)
        return rb
    monkeypatch.setattr(EB, "ribbon", gapped)
    probs = audit_mutant(tmp_path, *short_plan())
    assert any("walkable chain" in p or "off the walkable chain" in p for p in probs), probs


def test_missing_lanterns_are_caught(tmp_path, monkeypatch):
    real = EB.plan_trail

    def dark(*a, **k):
        p = real(*a, **k)
        p["posts"] = []
        return p
    monkeypatch.setattr(EB, "plan_trail", dark)
    probs = audit_mutant(tmp_path, *short_plan())
    assert any("lanterns" in p for p in probs), probs


def test_a_planner_that_ignores_every_rule_is_caught_on_the_trail_that_needs_them(tmp_path, monkeypatch):
    # with the open-cell test, the step rule and the climb cost all removed, the Craters line climbs a cliff step the
    # audit's own reading of the heightmap refuses (found by running it: the line is 73 blocks short of the adit)
    monkeypatch.setattr(EB.Window, "blocked", lambda self, x, z: not self.box.inside(x, z))
    monkeypatch.setattr(EB, "edge_ok", lambda win, a, b, rules: True)
    monkeypatch.setattr(EB, "CLIMB_WEIGHT", 0.0)
    plans, g, rules = EB.build_plans(only="trail_craters")
    pack, guides = write(tmp_path, plans, g, rules, "free")
    probs, _ = audit(pack, guides)
    assert any("trail_craters" in p and "walkable chain" in p for p in probs), probs


# ---------------------------------------------------------------------------- the audit's own instruments


def test_the_water_reading_finds_a_river_a_lake_and_the_sea():
    import ground as G
    from terrain import env_source_root
    import terrain as T
    g = G.Ground(env_source_root())
    w = AU.Water(int(T.sea_level(json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8")))))
    course = json.loads((ROOT / "data" / "rivers.json").read_text(encoding="utf-8"))["courses"][0]
    px, pz = course["graded_polyline"][len(course["graded_polyline"]) // 2][:2]
    assert any("river" in why for _x, _z, why in w.wet([(int(px), int(pz))], g)), "a river's own centre line is water"
    lm = next(l for l in json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]
              if (l.get("water_body") or {}).get("basin_polygons"))
    ring = lm["water_body"]["basin_polygons"][0]
    cx, cz = int(sum(p[0] for p in ring) / len(ring)), int(sum(p[1] for p in ring) / len(ring))
    assert any("lake" in why or "sea" in why or "river" in why for _x, _z, why in w.wet([(cx, cz)], g)), "a lake's middle is water"
    far = [(1522, 5292)]       # the Old Seams trail starts here, on the end of Pallet cross street: dry land
    assert w.wet(far, g) == []


def test_a_ribbon_cell_inside_a_placement_box_is_a_building_collision():
    boxes = AU.building_boxes("hometown")
    lab = next(r for r in json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
               if r["id"] == "hometown_oaks_lab")
    x, z = lab["position"]["x"] + 3, lab["position"]["z"] + 3
    assert AU.hit(boxes, [(x, z)]), "Oak's Lab is a building"
    assert not AU.hit(boxes, [(1600, 5300)]), "open ground east of Pallet is not"


def test_another_packs_write_counts_only_at_the_ribbons_own_height(tmp_path):
    base = tmp_path / "datapacks" / "other" / "data" / "x" / "function"
    base.mkdir(parents=True)
    (base / "f.mcfunction").write_text("setblock 100 70 100 minecraft:stone\nsetblock 101 -20 100 minecraft:diamond_ore\n"
                                       "fill 100 70 105 102 70 105 minecraft:stone replace minecraft:water\n", encoding="utf-8")
    boxes, n = AU.other_pack_boxes([(90, 90, 110, 110)], tmp_path / "datapacks")
    assert n == 1 and len(boxes) == 2, boxes          # the replace-fill is not a placement
    ground = lambda x, z: 70
    assert [c for c, _ in AU.hit(boxes, [(100, 100), (101, 100)], ground)] == [(100, 100)], \
        "stone at the ribbon's height collides; ore 90 blocks underneath does not"


def test_the_audit_refuses_an_incomplete_pack(tmp_path, good):
    probs, _ = AU.audit(tmp_path / "nothing", guide_pack=good[1], do_other_packs=False)
    assert probs and "run python tools/entrance_trails.py build" in probs[0]


# ---------------------------------------------------------------------------- registered in the apply path


def test_the_apply_path_knows_the_trail_step_and_both_packs():
    import reapply
    assert "cobblers_entrance_trails" in reapply.SERVER_PACKS and "cobblers_entrance_guides" in reapply.SERVER_PACKS
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'add("entrance_trails:build", "entrance_trails.py", "build", *src)' in src
    assert 'add("entrance_trails_audit", "entrance_trails_audit.py", *src)' in src
    assert '"R16T"' in src and 'cobblers:trails/%s' in src
    # R16T comes after the cave and mine carves and the shrines it keeps clear of
    order = [src.index(k) for k in ('"R9MN"', '"R9CS"', '"R16D"', '"R16T"')]
    assert order == sorted(order)
