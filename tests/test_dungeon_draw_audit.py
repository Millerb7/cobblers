"""The INDEPENDENT audit of the dungeon draw (tools/dungeon_draw_audit.py): tests of the audit itself, then the audit run on the
real generator and the real data.

Three kinds, and what each can and cannot show:

  * FIXTURE tests (seconds, no heightmap, no build): the audit's checkers run on a small synthetic world with answers worked out
    by hand in the test, so a checker that only works on the real surface fails here. They test the audit, not the draw.
  * REAL-DATA tests (seconds, need the heightmap): the audit's siting rules over data/dungeon_rips.json.
  * SIMULATOR tests (marked slow: the dungeon pack takes about five minutes to build): the generated draw functions run on
    tests/pocket_sim.py, then the same run against MUTATED COPIES OF tools/dungeon.py (data/ untouched), each of which the
    audit must fail. A mutation of the record would move the expectation and the output together and prove nothing.

Not covered, and not coverable here (testing.md: validity is not runtime behaviour): that `random value` and
`scoreboard players operation %=` behave on a server as the simulator models them, that the click advancement reaches its door
function in game, and that the oval stands where the siting says. Those are EXP-034's shape and a staging boot.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon_draw_audit as A  # noqa: E402


# ------------------------------------------------------------------------------------------------- the spec's expectations


def test_the_spec_table_counts_per_band_come_out_of_the_roster():
    # DUNGEON_DRAW.md 2.2 states the table by hand: bands 1-3 draw 5, band 4 draws 6, band 5 draws 11, band 6 draws 13.
    # Without this, the expectation the scenarios use could drift from the owner's approved table unseen.
    built = {d["id"] for d in json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))["dungeons"]}
    expect = A.roster_expectations(built_ids=built)
    counts = [len(A.eligible(b, set(A.ALL_FLAGS), expect)) for b in range(1, 7)]
    assert counts == [5, 5, 5, 6, 11, 13], counts


def test_eligibility_is_first_band_at_or_under_the_band_and_the_gate_held():
    # a hand-built roster: a floor of 4 behind gym 6, a floor of 5 behind gym 8. `<` for `<=` here is the slip the audit exists for
    exp = {"a": (1, None), "b": (4, "g6"), "c": (5, "g8")}
    assert A.eligible(1, {"g6", "g8"}, exp) == {"a"}
    assert A.eligible(4, set(), exp) == {"a"}
    assert A.eligible(4, {"g6"}, exp) == {"a", "b"}
    assert A.eligible(3, {"g6"}, exp) == {"a"}, "the gate does not lower the floor"
    assert A.eligible(5, {"g6"}, exp) == {"a", "b"}, "gym 6's flag is not gym 8's"
    assert A.eligible(5, {"g8"}, exp) == {"a", "c"}


def test_roster_prose_gates_are_read_to_their_flag_and_an_unreadable_one_fails_closed():
    # the roster writes 'gym8_cleared (proposed, ...)'; a gate the parser cannot read must stop the audit, not become "no gate"
    doc = {"dungeons": [{"id": "x", "first_band": 5, "gate": "gym8_cleared (proposed, Q13 OPEN)"},
                        {"id": "y", "first_band": 1, "gate": None},
                        {"id": "z", "first_band": 6, "gate": "champion_cleared (DUNGEONS.md 10)"}]}
    assert A.roster_expectations(doc) == {"x": (5, "gym8_cleared"), "y": (1, None), "z": (6, "champion_cleared")}
    with pytest.raises(ValueError):
        A.roster_expectations({"dungeons": [{"id": "w", "first_band": 5, "gate": "all eight badges"}]})


def test_every_band_of_the_real_roster_has_a_candidate():
    # DUNGEON_DRAW.md 3: "every band has at least one candidate"; with no candidate the draw falls back to the first dungeon
    built = {d["id"] for d in json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))["dungeons"]}
    expect = A.roster_expectations(built_ids=built)
    for b in range(1, 7):
        assert A.eligible(b, set(A.ALL_FLAGS), expect), b
    assert A.eligible(1, set(), expect) == {i for i, (fb, fl) in expect.items() if fb == 1 and fl is None}


def test_the_record_carries_the_rosters_first_band_and_gate_per_dungeon():
    # the owner took the roster's first bands and gates as written (DUNGEON_DRAW.md 5); a dungeon whose record drifted is drawn wrong
    doc = json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))
    expect = A.roster_expectations(built_ids={d["id"] for d in doc["dungeons"]})
    for d in doc["dungeons"]:
        fb, flag = expect[d["id"]]
        assert d["first_band"] == fb, d["id"]
        assert d["gate_flag"] == ("cobblers:flag/%s" % flag if flag else None), d["id"]
    assert doc["engine"]["lockout_ticks"] == 72000, "the spec's lockout is one hour of uptime"


# ------------------------------------------------------------------------------------------------- the checkers, on a synthetic world


SEA = 62
WORLD_LAKES = [(80, [[(200, 200), (220, 200), (220, 220), (200, 220)]])]


def flat(x, z):
    """The synthetic ground: y70 everywhere, a pit to y50 for x in 100..110 (under the sea), a lake bed at y70 under a level-80 lake."""
    return 50 if 100 <= x <= 110 else 70


def rip(x0, z, y=71, region="sq", kind="region", rid="rip_t"):
    return {"id": rid, "kind": kind, "region": region, "frame": {"x0": x0, "x1": x0 + 4, "z": z, "y": y, "height": 4},
            "click": [x0 + 2, y, z + 1], "outside": [x0 + 2.5, y, z + 3.5, 0]}


SQUARE = {"sq": [[(0, 0), (1000, 0), (1000, 1000), (0, 1000)]]}


def check(rips, points=(), boxes=(), regions=SQUARE, ground=flat, notes=None):
    return A.siting_problems(rips, ground, SEA, WORLD_LAKES, list(points), list(boxes), regions, notes=notes)


def test_the_footprint_is_the_plane_the_click_and_the_exit_point():
    # x0=500..504, z=500; the exit point is z 503.5, so its block is 503: the footprint is x500..504 z500..503
    assert A.footprint(rip(500, 500)) == (500, 500, 504, 503)


def test_a_clean_rip_on_dry_ground_passes_and_a_wet_one_is_named():
    assert check([rip(500, 500)]) == []
    wet = check([rip(100, 500, y=51)])           # ground y50 is under the sea at y62
    assert len(wet) == 1 and "under sea" in wet[0], wet
    lake = check([rip(204, 204)])                # ground y70 under a level-80 lake basin
    assert any("a lake" in p for p in lake), lake
    # a column above its lake's level is dry: the same basin with the level at 70 holds no water over y70 ground
    assert A.siting_problems([rip(204, 204)], flat, SEA, [(70, WORLD_LAKES[0][1])], [], [], SQUARE) == []


def test_the_plane_stands_on_the_ground_plus_one():
    assert any("frame.y" in p for p in check([rip(500, 500, y=80)]))
    assert check([rip(500, 500, y=71)]) == []


def test_clearance_is_measured_from_the_footprints_edge_and_thirty_passes():
    # footprint (500,500)-(504,503). A point 30.0 away along x passes; 29 fails; diagonals are Euclidean
    assert check([rip(500, 500)], points=[(534.0, 501.0, "f")]) == []
    near = check([rip(500, 500)], points=[(533.0, 501.0, "f")])
    assert len(near) == 1 and "29.0" in near[0], near
    assert check([rip(500, 500)], points=[(534.0, 507.0, "f")]) == []          # hypot(30, 4) = 30.27
    assert len(check([rip(500, 500)], points=[(529.0, 507.0, "f")])) == 1       # hypot(25, 4) = 25.3
    assert len(check([rip(500, 500)], points=[(502.0, 501.0, "f")])) == 1       # on the rip itself: distance 0


def test_a_test_trail_rip_is_exempt_from_clearance_only():
    t = rip(500, 500, kind="test_trail", y=71)
    assert check([t], points=[(505.0, 500.0, "f")]) == []
    assert check([rip(100, 500, y=51, kind="test_trail")]) != [], "a test rip is still held to dry ground"


def test_a_precinct_that_the_footprint_touches_is_named_and_a_block_of_air_is_not():
    assert check([rip(500, 500)], boxes=[(505, 500, 600, 600, "town x")]) == [], "one block clear of the town"
    hit = check([rip(500, 500)], boxes=[(504, 500, 600, 600, "town x")])
    assert len(hit) == 1 and "town x" in hit[0], hit


def test_a_footprint_corner_outside_its_region_is_named_and_a_missing_region_too():
    tight = {"sq": [[(0, 0), (503, 0), (503, 1000), (0, 1000)]]}      # x 500..504 sticks out past x503
    assert any("outside region" in p for p in check([rip(500, 500)], regions=tight))
    assert any("not in data/regions.json" in p for p in check([rip(500, 500, region=None)]))
    # a test rip's region defect is a note for the owner and not a failure
    notes = []
    assert check([rip(500, 500, kind="test_trail", region=None)], notes=notes) == [] and len(notes) == 1


def test_a_rip_inside_a_badge_gated_zone_is_named_and_one_beside_it_is_not():
    zones = {"zones": {"z2": {"name": "the deep", "pass": {"kind": "badges", "threshold": 8}, "boxes": [[490, 498, 510, 505]]},
                       "z3": {"name": "free", "pass": None, "boxes": [[0, 0, 1000, 1000]]}}}
    inside = A.gated_zone_problems([rip(500, 500, rid="rip_in")], zones)
    assert len(inside) == 1 and "rip_in" in inside[0] and "badges 8" in inside[0], inside
    assert A.gated_zone_problems([rip(511, 500)], zones) == []                     # footprint x511..515: one block clear
    assert len(A.gated_zone_problems([rip(510, 500)], zones)) == 1                 # x510 touches the box edge
    assert A.gated_zone_problems([rip(500, 520)], zones) == []                     # south of the box


def test_the_test_rips_positions_are_compared_by_dungeon_not_by_order():
    old = {"dungeons": [{"id": "a", "rip": {"frame": {"x0": 1}, "click": [1, 2, 3], "outside": [1.5, 2, 3.5, 0]}},
                        {"id": "b", "rip": {"frame": {"x0": 9}, "click": [9, 2, 3], "outside": [9.5, 2, 3.5, 0]}}]}

    def new(a_x, b_x):
        return [{"id": "rip_b", "kind": "test_trail", "legacy_dungeon": "b", "frame": {"x0": b_x}, "click": [b_x, 2, 3], "outside": [b_x + .5, 2, 3.5, 0]},
                {"id": "rip_a", "kind": "test_trail", "legacy_dungeon": "a", "frame": {"x0": a_x}, "click": [a_x, 2, 3], "outside": [a_x + .5, 2, 3.5, 0]}]
    assert A.old_test_rip_positions(old, new(1, 9)) == []
    moved = A.old_test_rip_positions(old, new(2, 9))
    assert moved and all("test rip for a" in p for p in moved), moved
    assert any("gone" in p for p in A.old_test_rip_positions(old, new(1, 9)[:1]))


def test_authored_points_reads_xz_dicts_pairs_and_triples_but_not_boxes(tmp_path):
    d = tmp_path / "data"
    (d / "sub").mkdir(parents=True)
    (d / "a.json").write_text(json.dumps({"p": {"x": 10, "z": 20}, "q": [30, 40], "r": [50, 99, 60], "box": [1, 2, 3, 4],
                                          "cc": {"cx": 70, "cz": 80}, "off": [9000, 5]}), encoding="utf-8")
    (d / "sub" / "b.json").write_text(json.dumps({"x": 100, "z": 200}), encoding="utf-8")
    (d / "skip.json").write_text(json.dumps({"x": 1, "z": 1}), encoding="utf-8")
    got = sorted((x, z, f) for x, z, f in A.authored_points(d, skip_files=("data/skip.json",)))
    assert got == [(10.0, 20.0, "data/a.json"), (30.0, 40.0, "data/a.json"), (50.0, 60.0, "data/a.json"),
                   (70.0, 80.0, "data/a.json"), (100.0, 200.0, "data/sub/b.json")]


def test_a_rips_click_function_is_found_by_the_tag_the_advancement_listens_for():
    adv = {"criteria": {"click": {"trigger": "t", "conditions": {"entity": [{"predicate": {"nbt": '{Tags:["tagA"]}'}}]}}},
           "rewards": {"function": "cobblers:dungeons/door/whatever"}}
    files = {"data/cobblers/advancement/dungeons/rip_x.json": json.dumps(adv),
             "data/cobblers/function/dungeons/rips/entities.mcfunction":
                 'summon minecraft:interaction 10.5 64 20.5 {width:3.0f,Tags:["dg.rip","tagA","dg.rip_new"]}\n'
                 'summon minecraft:interaction 99.5 64 99.5 {width:3.0f,Tags:["tagZ"]}\n'}
    rips = [{"id": "r1", "click": [10, 64, 20]}, {"id": "r2", "click": [99, 64, 99]}, {"id": "r3", "click": [1, 1, 1]}]
    assert A.rip_click_functions(files, rips) == {"r1": "cobblers:dungeons/door/whatever"}, "r2's tag has no advancement, r3 has no interaction"


def test_a_rotation_window_must_hold_each_wanted_dungeon_once():
    want = {"a", "b", "c"}
    assert A._permutation_windows(["a", "b", "c", "a", "b", "c", "a"], want) == []
    assert A._permutation_windows(["a", "b", "c", "c", "a", "b"], want) != [], "c twice in a row"
    assert A._permutation_windows(["a", "b", "a", "b", "c"], want) != [], "a returns before c is seen"


def test_every_mutation_targets_exactly_one_spot_of_the_generator_source():
    # a mutation that finds its text twice or not at all is no longer a mutation of the draw: the audit's independence proof
    # would silently go stale when the generator is edited
    src = (ROOT / "tools" / "dungeon.py").read_text(encoding="utf-8")
    for name, m in A.MUTATIONS.items():
        old, new = m["edit"]
        assert src.count(old) == 1, "%s: target occurs %d times" % (name, src.count(old))
        assert old != new, name


def test_a_mutation_whose_target_is_gone_refuses_to_load_and_is_not_loosened(monkeypatch):
    monkeypatch.setitem(A.MUTATIONS, "stale", {"why": "x", "edit": ("this text is nowhere in dungeon.py", "y")})
    with pytest.raises(RuntimeError, match="update the mutation"):
        A.load_module("stale")


def test_a_mutation_counts_as_caught_only_by_a_problem_the_control_did_not_have():
    base = {"a": ["old defect"], "b": []}
    assert A.novel(base, {"a": ["old defect"], "b": []}) == {}, "a defect the real generator already has proves nothing"
    assert A.novel(base, {"a": ["old defect", "new"], "b": []}) == {"a": ["new"]}
    assert A.novel(base, {"a": ["old defect"], "b": ["boom"]}) == {"b": ["boom"]}


# ------------------------------------------------------------------------------------------------- real data, heightmap


def _have_heightmap():
    try:
        import ground as G
        G.load()
        return True
    except Exception:
        return False


needs_heightmap = pytest.mark.skipif(not _have_heightmap(), reason="the canonical heightmap is not reachable (COBBLERS_SOURCE_ROOT / .claude/settings.json)")


@pytest.fixture(scope="module")
def siting():
    out = {}
    return A.run_siting(out), out


def _without_gated(problems):
    return [p for p in problems if "rift zone" not in p]


@needs_heightmap
def test_the_real_rips_are_dry_clear_of_authored_coordinates_outside_precincts_and_inside_their_region(siting):
    # DUNGEON_DRAW.md 2.6, measured from tools/ground.py round(h) and data/*.json read by the audit, not by tools/dungeon_rips.py
    problems, out = siting
    assert out["siting"]["rips"] == 31 and out["siting"]["region_rips"] == 18
    assert _without_gated(problems) == []


@needs_heightmap
@pytest.mark.xfail(strict=True, reason="FINDING 2026-10-13: rip_the_rift stands inside data/rift_zones.json zone z2 (a badge-8 pass, full height): "
                                       "a player short of 8 badges is turned back from its every column, so it is no find for bands 1-4 "
                                       "and DUNGEON_DRAW.md 5's staging step 2 (a band-1 click at rip_the_rift) cannot work. Remove this mark when the rip moves.")
def test_no_rip_stands_inside_a_badge_gated_rift_zone(siting):
    problems, _ = siting
    assert [p for p in problems if "rift zone" in p] == []


@needs_heightmap
def test_the_siting_audit_reads_a_real_number_of_authored_points(siting):
    # an audit that read no points would pass every clearance: the walk over data/ must find tens of thousands
    _, out = siting
    assert out["siting"]["points_read"] > 20000, out["siting"]


@needs_heightmap
def test_the_cli_writes_its_full_result_to_the_file_and_prints_one_verdict_line(capsys, tmp_path):
    # the output contract: a long result never lands in the transcript (CLAUDE.md "Context cost"), one line does
    out = tmp_path / "result.json"
    rc = A.main(["--only", "siting", "--out", str(out)])
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1 and lines[0].split(":")[0] in ("PASS", "FAIL"), lines
    assert (rc == 0) == lines[0].startswith("PASS")
    got = json.loads(out.read_text(encoding="utf-8"))
    assert {"siting", "siting_problems", "siting_notes"} <= set(got)


@needs_heightmap
def test_the_siting_tool_refuses_sites_made_to_break_one_rule_each():
    # tools/dungeon_rips.py is handed a too-near coordinate, a town beside the plane, a foreign region, a neighbour rip and a sea
    # floor, with the spec's distances (30, 300). Without this, a siting tool that approves everything passes `check` forever.
    assert A.sc_siting_tool_rejects_sites_that_break_a_rule(A.load_rips_module(None)) == []


@needs_heightmap
@pytest.mark.parametrize("mutation", sorted(A.RIPS_MUTATIONS))
def test_the_audit_fails_when_the_siting_tool_is_mutated(mutation):
    # independence for the siting tool: tools/dungeon_rips.py edited at one spot, data/ untouched, and the audit must object
    got = A.sc_siting_tool_rejects_sites_that_break_a_rule(A.load_rips_module(mutation))
    assert got, "MISSED: %s (%s)" % (mutation, A.RIPS_MUTATIONS[mutation]["why"])


def test_every_siting_mutation_targets_exactly_one_spot_of_the_tool_source():
    src = (ROOT / "tools" / "dungeon_rips.py").read_text(encoding="utf-8")
    for name, m in A.RIPS_MUTATIONS.items():
        assert src.count(m["edit"][0]) == 1, name


def test_the_13_test_rips_have_not_moved_since_the_owner_played_them():
    # git show 6249332e: data/dungeons.json carried each dungeon's rip; the 13 test rips must stand where those records put them
    r = subprocess.run(["git", "show", "%s:data/dungeons.json" % A.OLD_TEST_RIPS_COMMIT], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("commit %s is not in this checkout: %s" % (A.OLD_TEST_RIPS_COMMIT, r.stderr.strip()[:120]))
    rips = json.loads((ROOT / "data" / "dungeon_rips.json").read_text(encoding="utf-8"))["rips"]
    assert A.old_test_rip_positions(json.loads(r.stdout), rips) == []


# ------------------------------------------------------------------------------------------------- the simulator (slow)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    got, facts = A.run_draw(A.load_module(None), tmp_path_factory.mktemp("draw_audit"))
    return got, facts


SCENARIO_NAMES = [n for n, _ in A.SCENARIOS] + ["reapply_wires_r16dr"]


@pytest.mark.slow
@pytest.mark.parametrize("scenario", SCENARIO_NAMES)
def test_the_generated_draw_holds_the_specs_property(baseline, scenario):
    # each scenario's docstring and name say the property; its expectations come from the spec and the roster
    got, _ = baseline
    assert "contract_names" not in got, got.get("contract_names")
    assert scenario in got, "scenario did not run"
    assert got[scenario] == []


@pytest.mark.slow
@pytest.mark.parametrize("mutation", sorted(A.MUTATIONS))
def test_the_audit_fails_when_the_generator_is_mutated(baseline, mutation, tmp_path):
    # independence: the generator (tools/dungeon.py source) is edited at one spot, data/ untouched, and the audit must object
    # with a problem the unmutated run did not have. A mutation that passes is a property the audit does not hold.
    got, _ = A.run_draw(A.load_module(mutation), tmp_path)
    assert A.novel(baseline[0], got), "MISSED: %s (%s)" % (mutation, A.MUTATIONS[mutation]["why"])
