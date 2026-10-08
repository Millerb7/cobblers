"""tools/ambient_composition_audit.py against a synthetic four-town fixture with hand-computed expectations.

The fixture (tests/fixtures/ambient_composition/) is `pass/` -- four towns that satisfy every rule at the
real thresholds copied from data/ambient.json -- plus one `fail_<rule>/` overlay per rule, holding only the
files that differ. Each fail test asserts its rule FAILS and every other check in the layer PASSES, so a
fixture cannot pass by tripping a neighbouring rule.

    alpha   hamlet  10 = 3 working / 1 pet / 2 placed / 4 in situations (3 Psyduck + 1 Munchlax)
    bravo   outpost  6 = 2 / 1 / 1 / 2
    charlie hamlet  12 = 3 / 2 / 2 / 5
    delta   town    40 = 20 / 3 / 5 / 12, the mining town (working 0.50)

What this does NOT cover: whether the generator's output reaches the world, renders, holds its pose, or
holds frame rate. Those are in-game checks (composition.ceiling.why names the server cost as unmeasured).
"""
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ambient_composition_audit as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "ambient_composition"
DATA_CHECKS = ["scope_files", "fields", "counts_claim", "target", "size_band", "ceiling", "ratios",
               "situations_floor", "mining_working", "unique_situation", "situations_distinct",
               "species_spread", "roster_overlap", "species_in_jar", "species_not_atm"]
PLACEMENT_CHECKS = ["plan_entries", "plan_counts", "same_species_radius", "in_view"]


def build(tmp_path, overlay=None):
    """The pass fixture copied to tmp, the overlay's files laid over it, and a jar built from its species."""
    root = tmp_path / "fx"
    shutil.copytree(FIX / "pass", root)
    if overlay:
        shutil.copytree(FIX / overlay, root, dirs_exist_ok=True)
    jar = tmp_path / "Cobblemon-fabric-1.8.0+1.21.1.jar"
    with zipfile.ZipFile(jar, "w") as z:
        for sp in json.loads((root / "jar_species.json").read_text()):
            z.writestr(f"data/cobblemon/species/generation0/{sp}.json",
                       json.dumps({"name": sp.capitalize(), "implemented": True}))
        z.writestr("data/cobblemon/species/generation0/unfinished.json",
                   json.dumps({"name": "Unfinished", "implemented": False}))
    return root, jar


def audit(root, jar, layer="all", plan=None):
    return A.run(rules_path=root / "rules.json", towns_dir=root / "towns",
                 plans=[plan or root / "plan.json"], town_plans=root / "town_plans", jar=jar,
                 atm=root / "atm.json", layer=layer)


def by_name(report):
    return {c["check"]: c for c in report["checks"]}


def only_fails(report, name):
    """The named check fails and every other check in the report passes."""
    checks = by_name(report)
    assert checks[name]["status"] == A.FAIL, checks[name]
    others = {n: c["status"] for n, c in checks.items() if n != name and c["status"] != A.PASS}
    assert others == {}, {n: checks[n]["problems"] or checks[n].get("reason") for n in others}
    return checks[name]["problems"]


# Without this the fixture could be failing quietly, and every "fails only its rule" test would be vacuous.
def test_the_pass_fixture_passes_every_check_in_both_layers(tmp_path):
    report = audit(*build(tmp_path))
    assert report["verdict"] == A.PASS, [c for c in report["checks"] if c["status"] != A.PASS]
    assert [c["check"] for c in report["checks"]] == DATA_CHECKS + PLACEMENT_CHECKS
    assert report["counts"]["delta"] == {"working": 20, "pets": 3, "placed": 5, "situations": 12, "total": 40}


# Without this an audit could read the claimed counts instead of the records.
def test_counts_are_rederived_and_a_wrong_claim_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_counts_claim"), layer="data"), "counts_claim")
    assert problems == ["alpha: counts.pets claims 2, the records give 1"]


# Without this a settlement in scope could have no town file and the audit would check nothing for it.
def test_a_stray_town_file_outside_scope_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_scope_files"), layer="data"), "scope_files")
    assert problems == ["zulu: town file outside composition.scope"]


# Without this a town missing its file would pass by having nothing to check (audits fail closed).
def test_a_missing_town_file_fails_scope_files(tmp_path):
    root, jar = build(tmp_path)
    (root / "towns" / "bravo.json").unlink()
    checks = by_name(audit(root, jar, layer="data"))
    assert checks["scope_files"]["status"] == A.FAIL
    assert checks["scope_files"]["problems"][0].startswith("bravo: no town file")


# Without this an empty town folder would report thirteen vacuous passes beside one failure.
def test_no_town_files_leaves_every_rule_unchecked_not_passed(tmp_path):
    root, jar = build(tmp_path)
    shutil.rmtree(root / "towns")
    checks = by_name(audit(root, jar))
    assert checks["scope_files"]["status"] == A.FAIL
    assert [n for n in DATA_CHECKS[1:] if checks[n]["status"] == A.PASS] == []
    assert checks["plan_counts"]["status"] == A.NOT_CHECKED and len(checks["plan_counts"]["not_checked"]) == 4


# Without this a pet mode the generator does not know would reach it unflagged.
def test_a_pet_mode_outside_the_schema_fails_fields(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_fields"), layer="data"), "fields")
    assert problems == ["alpha: pets[0] (alpha_pet_00) mode 'sit' not in ['follow', 'wait']"]


# Without this a town's declared target could drift from what it actually places.
def test_a_target_unlike_the_records_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_target"), layer="data"), "target")
    assert problems == ["alpha: target 12 but the records total 10"]


# Without this a 10-Pokemon town could call itself an outpost (band 3-6) unnoticed.
def test_a_total_outside_its_size_band_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_size_band"), layer="data"), "size_band")
    assert problems == ["alpha: total 10 outside the outpost band [3, 6]"]


# Without this the ceiling would be a constant: lowering per_town in the rules file must change the verdict.
def test_the_ceiling_is_read_from_the_rules_file(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_ceiling"), layer="data"), "ceiling")
    assert problems == ["alpha: total 10 over ceiling.per_town 9", "charlie: total 12 over ceiling.per_town 9",
                        "delta: total 40 over ceiling.per_town 9"]


# Without this a town with no pets and too many placed would pass the 30/15/20/35 composition.
def test_shares_outside_target_plus_tolerance_fail(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_ratios"), layer="data"), "ratios")
    # the fixture's rules carry no tolerance_pokemon, so the band is the plain 0.08
    assert problems == ["alpha: pets 0/10 = 0.000, outside 0.150 +- 0.080",
                        "alpha: placed 3/10 = 0.300, outside 0.200 +- 0.080"]


# Without this situations at 4/14 = 0.286 would pass: inside 0.35 +- 0.08 but under the owner's 0.30 floor.
def test_situations_under_the_floor_fail_even_inside_the_band(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_situations_floor"), layer="data"), "situations_floor")
    assert problems == ["charlie: situations 4/14 = 0.286, under 0.3"]


# Without this a mining town could work at 19/40 = 0.475 and pass on the ordinary working band.
def test_a_mining_town_under_working_min_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_mining_working"), layer="data"), "mining_working")
    assert len(problems) == 1 and problems[0].startswith("delta: working 19/40 = 0.475, under working_min 0.5")


# Without this a town could have only shared, generic situations.
def test_a_town_without_a_unique_situation_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_unique_situation"), layer="data"), "unique_situation")
    assert problems == ["bravo: no situation marked unique: true"]


# Without this two towns could carry the same situation under different capitalisation.
def test_two_towns_with_one_situation_title_fail(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_situations_title"), layer="data"), "situations_distinct")
    assert problems == ["bravo/bravo_queue and alpha/alpha_garden share the same title "
                        "('A Psyduck Takeover in the Back Garden!')"]


# Without this a situation could be copied under a new title (the props differ only in block state).
def test_two_towns_with_one_species_and_prop_set_fail(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_situations_set"), layer="data"), "situations_distinct")
    assert problems == ["charlie/charlie_laundry and alpha/alpha_garden share the same species and props "
                        "(['psyduck'], ['minecraft:rose_bush'])"]


# Without this one species could be in every town again (Snorlax was in 13 of 16).
def test_a_species_in_more_than_three_towns_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_species_spread"), layer="data"), "species_spread")
    assert problems == ["eevee in 4 towns ['alpha', 'bravo', 'charlie', 'delta'], over 3"]


# Without this two towns could share a roster (Viltri Quay and Sunset West shared 0.52).
def test_rosters_overlapping_over_the_limit_fail(tmp_path):
    report = audit(*build(tmp_path, "fail_roster_overlap"), layer="data")
    problems = only_fails(report, "roster_overlap")
    assert problems == ["alpha and charlie: roster Jaccard 3/14 = 0.214, over 0.2 (shared ['natu', 'vulpix', "
                        "'zubat'])"]


# Without this a species the 1.8.0 jar does not implement would spawn nothing in game.
def test_a_species_absent_from_the_jar_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_species_in_jar"), layer="data"), "species_in_jar")
    assert problems == ["missingno (in ['bravo']) is not an implemented species in "
                        "Cobblemon-fabric-1.8.0+1.21.1.jar"]


# Without this the species check would silently pass on a machine with no jar.
def test_no_jar_skips_by_name_and_never_passes(tmp_path):
    root, _ = build(tmp_path)
    report = audit(root, tmp_path / "absent.jar", layer="data")
    jar = by_name(report)["species_in_jar"]
    assert jar["status"] == A.SKIPPED and "absent.jar is not a file" in jar["reason"]
    assert report["verdict"] != A.PASS


# Without this a species whose model comes from the ATM subset could be used as a town ambient.
def test_a_species_in_the_atm_subset_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_species_not_atm"), layer="data"), "species_not_atm")
    assert problems == ["gulpin (in ['bravo']) is in the ATM client-model subset"]


# Without this one generator could stack two of a species side by side outside any situation.
def test_two_of_one_species_within_the_group_radius_fail(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_same_species")), "same_species_radius")
    assert problems == ["delta: geodude delta_work_00 (worker) and delta_work_05 (worker) 3.00 blocks apart, "
                        "within 4, not members of one situation"]


# Without this the situation exemption could cover members of DIFFERENT situations.
def test_the_group_exemption_needs_the_same_situation(tmp_path):
    root, jar = build(tmp_path)
    plan = json.loads((root / "plan.json").read_text())
    plan["towns"]["alpha"][7]["situation"] = "alpha_apples"   # alpha_psyduck_1, 1 block from psyduck_0
    (root / "plan.json").write_text(json.dumps(plan))
    checks = by_name(audit(root, jar))
    assert checks["same_species_radius"]["status"] == A.FAIL
    assert len(checks["same_species_radius"]["problems"]) == 2    # psyduck_1 against psyduck_0 and psyduck_2


# Without this a crowd near one standing point would pass on the town's total alone. 20 workers 2 apart
# along x plus the 6-Trapinch situation beside them: all 26 within 24 of (2024.5, 22.5).
def test_more_than_in_view_max_near_one_point_fails(tmp_path):
    report = audit(*build(tmp_path, "fail_in_view"))
    problems = only_fails(report, "in_view")
    assert len(problems) == 1 and problems[0].startswith("delta: 26 Pokemon within 24 blocks")
    assert by_name(report)["in_view"]["worst"]["delta"]["max"] == 26


# Without this the sampling could miss: in the pass fixture delta's workers are 6 apart, so 9 (offsets
# -24..24) are the most within 24 of any point -- a hand count the grid has to reproduce exactly.
def test_in_view_count_matches_the_hand_count(tmp_path):
    worst = by_name(audit(*build(tmp_path)))["in_view"]["worst"]
    assert worst["delta"]["max"] == 9
    assert worst["delta"]["samples"] == 200 * 200


# Without this the generator could drop a Pokemon the town file authors and the audit would not notice.
def test_a_plan_missing_an_authored_pokemon_fails(tmp_path):
    problems = only_fails(audit(*build(tmp_path, "fail_plan_counts")), "plan_counts")
    assert problems == ["alpha: the plan places 9, the town file's records total 10"]


# Without this a plan entry with no position would be skipped and every placement rule would pass over it.
def test_a_plan_entry_without_a_position_fails(tmp_path):
    root, jar = build(tmp_path)
    plan = json.loads((root / "plan.json").read_text())
    del plan["towns"]["bravo"][0]["at"]
    (root / "plan.json").write_text(json.dumps(plan))
    checks = by_name(audit(root, jar))
    assert checks["plan_entries"]["status"] == A.FAIL
    assert checks["plan_entries"]["problems"] == ["plan.json: bravo_mudbray lacks position"]


# Without this a stationary worker (position under `start`, as tools/ambient.py writes it) would read as
# positionless, and a place outside the scope (Pallet, the farm) would be held to the town rules.
def test_stationary_workers_are_read_and_places_outside_scope_are_listed_not_judged(tmp_path):
    root, jar = build(tmp_path)
    plan = json.loads((root / "plan.json").read_text())
    plan["workers"] += [{"id": f"zulu_w{k}", "settlement": "zulu", "species": "machop", "job": "work",
                         "start": [5000.5 + k, 64, 5000.5]} for k in range(2)]
    (root / "plan.json").write_text(json.dumps(plan))
    checks = by_name(audit(root, jar))
    assert checks["plan_entries"]["status"] == A.PASS and checks["plan_entries"]["entries"] == 70
    assert checks["same_species_radius"]["status"] == A.PASS
    assert checks["plan_counts"]["outside_scope"] == ["zulu"]


# Without this an absent generator output would let the placement layer pass by having nothing to check.
def test_missing_generator_output_is_not_checked_by_name(tmp_path):
    root, jar = build(tmp_path)
    report = audit(root, jar, plan=tmp_path / "no_such_plan.json")
    placement = [c for c in report["checks"] if c["layer"] == "placement"]
    assert [c["check"] for c in placement] == PLACEMENT_CHECKS
    assert all(c["status"] == A.NOT_CHECKED and "no_such_plan.json" in c["reason"] for c in placement)
    assert report["verdict"] == A.NOT_CHECKED


# Without this a town with no plan footprint would be left out of the in-view sweep and pass.
def test_a_town_without_a_footprint_is_not_checked_by_name(tmp_path):
    root, jar = build(tmp_path)
    (root / "town_plans" / "bravo_plan.json").unlink()
    in_view = by_name(audit(root, jar))["in_view"]
    assert in_view["status"] == A.NOT_CHECKED
    assert in_view["not_checked"][0].startswith("bravo: no footprint")


# Without this the CLI could print success while a layer was unchecked: exit 2, one summary line, a report.
def test_cli_writes_the_report_and_exits_by_verdict(tmp_path, capsys):
    root, jar = build(tmp_path)
    args = ["--rules", str(root / "rules.json"), "--towns-dir", str(root / "towns"),
            "--town-plans", str(root / "town_plans"), "--jar", str(jar), "--atm", str(root / "atm.json"),
            "--report", str(tmp_path / "report.json")]
    assert A.main(args + ["--plan", str(root / "plan.json")]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("ambient composition audit: PASS")
    assert A.main(args + ["--plan", str(tmp_path / "absent.json")]) == 2
    out = capsys.readouterr().out
    assert "NOT_CHECKED placement/in_view" in out
    assert json.loads((tmp_path / "report.json").read_text())["verdict"] == A.NOT_CHECKED


# Without this the floor would be a constant: it is parsed from the rules' own text, and a rules file
# that stops stating it fails the check instead of assuming 0.30.
def test_the_situations_floor_comes_from_the_rules_text(tmp_path):
    root, jar = build(tmp_path)
    rules = json.loads((root / "rules.json").read_text())
    assert A.load_rules(root / "rules.json")["situations_floor"] == 0.3
    rules["composition"]["ratios"]["why"] = "no floor stated"
    (root / "rules.json").write_text(json.dumps(rules))
    floor = by_name(audit(root, jar, layer="data"))["situations_floor"]
    assert floor["status"] == A.FAIL and "cannot be read" in floor["problems"][0]


# Without this the audit could drift from the committed rules: every threshold is the value in data/ambient.json.
def test_the_committed_rules_load_with_their_own_values():
    comp = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))["composition"]
    r = A.load_rules(ROOT / "data" / "ambient.json")
    assert r["per_town"] == comp["ceiling"]["per_town"] and r["in_view_max"] == comp["ceiling"]["in_view_max"]
    assert r["group_radius"] == comp["variety"]["same_species_group_radius"]
    assert r["scope"] == comp["scope"] and r["mining"] == comp["mining_towns"]["settlements"]
    assert r["pet_modes"] and r["spots"] and r["poses"]


# Without this the rules' arithmetic limits would stay invisible. Hand-computed from 30/15/20/35 +- 0.08,
# floor 0.30, mining working >= 0.50: an outpost admits only 6 (2/1/1/2); a mining town admits only 40
# (20/3/5/12); no mining hamlet or outpost admits any total.
# Without this the rules could again be unmeetable in whole numbers (2026-10-05, before tolerance_pokemon and the
# mining rest split: an outpost could total only 6, a mining town only 40, and no mining hamlet at all).
def test_every_total_in_every_size_band_admits_a_split():
    r = A.load_rules(ROOT / "data" / "ambient.json")
    scale = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))["composition"]["scale"]
    for size, band in scale.items():
        if size == "why":
            continue
        for mining in (False, True):
            got = A.feasible_totals(band[0], band[1], r, mining=mining)
            assert sorted(got) == list(range(band[0], band[1] + 1)), (size, mining, sorted(got))


# Without this a form or a namespaced id would count as a new species and dodge the variety rules.
def test_species_and_block_identity_ignore_namespace_form_and_state():
    assert A.species_key("cobblemon:mrmime galarian") == A.species_key("Mr. Mime", properties=False) == "mrmime"
    assert A.species_key("Type: Null", properties=False) == A.species_key("typenull") == "typenull"
    assert A.species_key("cobblemon:Nidoran♀") == "nidoranf"
    assert A.block_key("rose_bush[half=lower]") == A.block_key("minecraft:rose_bush")
