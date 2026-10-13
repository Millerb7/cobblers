"""The Scar Tarn's independent audit (tools/scar_tarn_audit.py), three ways:

  synthetic   a 15 x 15 heightmap with a 5 x 5 bowl and hand-written functions, every expected number computed by hand
              in the test's comment: the replay's modes, the forceload rule, gravity, the open faces, the flow, the pond
              checks, the alpha rules against a hand-made jar, and the overlap sweep against a hand-made data folder.
  real        the generator's own pack, built with its CLI, replayed over the canonical heightmap: no finding.
  mutations   the GENERATOR's source is mutated (data/scar_tarn.json untouched), run through its own CLI, and the audit
              must name the fault. The baseline run is clean, so each finding is the mutation's.

Not covered: anything in a running world (the fills landing, ice, the alpha flag, the re-levelling sensor); the
heightmap stands in for the save. The real and mutation tests skip, naming why, without the heightmap or the jar.
"""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import scar_tarn_audit as A  # noqa: E402

GEN = ROOT / "tools" / "scar_tarn.py"
DOC = json.loads((ROOT / "data" / "scar_tarn.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------- synthetic fixture
def bowl(rim=10, floor=6, ring=None):
    """x100..114 z200..214 at `rim`; the 5 x 5 bowl x104..108 z204..208 at `floor`; `ring` (if given) for the 8-ring."""
    H = np.full((15, 15), rim, int)
    if ring is not None:
        H[3:10, 3:10] = ring
    H[4:9, 4:9] = floor
    return A.Heights(H, 100, 200)


FORCE = "forceload add 96 192 127 223"
POND = [FORCE, "fill 104 6 204 108 6 208 minecraft:clay", "fill 104 7 204 108 8 208 minecraft:water"]
SDOC = {"pond": {"water_level": 8, "seed": [106, 206], "window": [100, 200, 114, 214], "bank_lift_to": 9},
        "rules": {"authored_clearance": 24}}


def stats(lines, H, drops=(0, 1, 2, 3)):
    rep = A.Report()
    return A.check_water(lines, H, SDOC, rep, drops), rep


def test_a_held_pond_has_no_open_face_until_the_ground_drops_under_the_water():
    # removing this lets a replay that never lowers the unwritten ground pass a pond the export could drain.
    # 50 water blocks; rim ground 10, so at drop 3 the rim's y8 is air: 5 x 4 = 20 side faces open at y8, and the
    # water spreads over the flat rim (ground 7) until it reaches the heightmap's edge, 4 blocks out: an escape.
    st, rep = stats(POND, bowl())
    assert [st[d]["open_faces"] for d in (0, 1, 2, 3)] == [0, 0, 0, 20]
    assert st[0]["water"] == 50 and st[0]["reached"] == 0
    assert st[3]["escaped"] and st[3]["falls"] == 0
    assert any("drop 3" in f and "LEAVES the window" in f for f in rep.findings)


def test_a_notch_in_the_rim_is_named_and_the_flow_follows_it_down():
    # removing this lets a rim with a hole pass because the hole is only one block. (103, 206) at ground 7 opens
    # (104, 8, 206)'s west face; (102, 206) at ground 5 behind it: the water enters (103, 8, 206), (102, 8, 206), falls
    # through (102, 7, 206) to (102, 6, 206) and stops: 4 cells reached, 2 over a free cell, inside the window.
    H = bowl()
    H.A[6, 3], H.A[6, 2] = 7, 5
    st, rep = stats(POND, H, drops=(0,))
    assert st[0]["open_faces"] == 1 and st[0]["reached"] == 4 and st[0]["falls"] == 2 and not st[0]["escaped"]
    assert any("(104, 8, 206)->(103, 8, 206) side" in f for f in rep.findings)


def test_a_leak_at_drop_two_that_stays_put_is_noted_not_failed():
    # removing this turns every pocket under a floating bank block into a failure the real tarn has by design (17
    # cells at drop 2, held). The 8-ring (x103..109 z203..209 less the bowl: 24 columns) at ground 9, the outside at
    # 12. At drop 2 the ring's y8 is air over ground 7: 20 faces open; the water fills the whole ring at y8 (the four
    # corners from their sides), 24 cells, and the outside (ground 10 at drop 2) stops it. Nothing falls.
    H = bowl(rim=12, ring=9)
    st, rep = stats(POND, H, drops=(2,))
    assert st[2]["open_faces"] == 20 and st[2]["reached"] == 24 and st[2]["falls"] == 0
    assert not rep.findings and any("held: no fall, no escape" in n for n in rep.notes)


def test_keep_and_replace_filters_follow_the_command_not_the_intent():
    # removing this lets the replay place a `keep` block over ground, so a bank that never lands would hold water.
    lines = [FORCE, "setblock 101 10 201 minecraft:moss_block keep", "setblock 101 11 201 minecraft:fern keep",
             "fill 101 11 202 101 11 202 minecraft:podzol replace minecraft:snow", "setblock 101 13 203 minecraft:gravel"]
    W, probs = A.replay(lines, bowl(), 0)
    assert not probs
    assert W.get(101, 10, 201) == A.GROUND
    assert W.get(101, 11, 201) == "minecraft:fern"
    assert W.get(101, 11, 202) == A.AIR
    # gravity: the gravel written at y13 over air at y11-12 rests on the ground at y11
    assert W.get(101, 11, 203) == "minecraft:gravel" and W.get(101, 13, 203) == A.AIR


def test_a_write_in_a_chunk_nothing_holds_is_a_problem_and_lands_nowhere():
    # removing this lets a function whose forceload misses a chunk pass with water the server never placed.
    W, probs = A.replay(["fill 104 7 204 108 8 208 minecraft:water"], bowl(), 0)
    assert probs and "forceload" in probs[0] and not A.water_cells(W)


def test_an_unknown_command_is_a_problem_not_a_skip():
    # removing this lets a command the replay cannot read drop out of the world silently.
    _W, probs = A.replay([FORCE, "clone 1 2 3 4 5 6 7 8 9"], bowl(), 0)
    assert probs and "not a command" in probs[0]


def test_the_pond_checks_hold_on_a_clean_bowl():
    # removing this hides a pond rule that fails on a correct pond. The bowl holds to y10 (the flood at y11 reaches the
    # edge): margin 10 - 8 = 2; the rim stands at ground 10, so it holds at bank_lift_to 9.
    H = bowl()
    assert A.highest_held(H, (106, 206), (100, 200, 114, 214), 8) == 10
    rep = A.Report()
    W, _ = A.replay(POND, H, 0)
    A.check_pond(W, A.water_cells(W), H, SDOC, rep)
    assert rep.findings == []


@pytest.mark.parametrize("extra,expect", [
    # a trunk stood in the water at (106, 206): its two water cells y7, y8 become log
    (["fill 106 7 206 106 12 206 minecraft:spruce_log"], "2 cell(s) of the pond are not water"),
    # one water block over the level
    (["setblock 106 9 206 minecraft:water"], "1 water block(s) over the level y8"),
    # water in a column the heightmap's pond does not have
    (["setblock 101 11 201 minecraft:water"], "1 water column(s) outside the heightmap's pond"),
])
def test_the_pond_is_the_heightmaps_pond_and_nothing_stands_in_it(extra, expect):
    # removing this lets a tree in the water, a raised surface or stray water pass a containment check that only asks
    # whether each water block is held.
    H = bowl()
    W, _ = A.replay(POND + extra, H, 0)
    rep = A.Report()
    A.check_pond(W, A.water_cells(W), H, SDOC, rep)
    assert any(expect in f for f in rep.findings), rep.findings


def test_a_rim_at_the_water_level_without_its_lift_is_named():
    # removing this lets the bank lift go missing: the water is still held at drop 0, so only this sees it. The
    # 8-ring at ground 8 = the level; the 20 rim columns 4-adjacent to the pond are air at bank_lift_to 9. With a moss
    # course written at y9 over the ring they hold. The hollow holds to 10 (the outer ground): margin 2.
    H = bowl(ring=8)
    W, _ = A.replay(POND, H, 0)
    rep = A.Report()
    A.check_pond(W, A.water_cells(W), H, SDOC, rep)
    assert [f for f in rep.findings if "rim column" in f] and "20 rim column(s) of 20" in " ".join(rep.findings)
    W, _ = A.replay(POND + ["fill 103 9 203 109 9 209 minecraft:moss_block keep"], H, 0)
    rep = A.Report()
    A.check_pond(W, A.water_cells(W), H, SDOC, rep)
    assert rep.findings == []


def test_too_little_freeboard_is_named():
    # removing this lets the water level creep up to the hollow's own spill. Outer ground 9: the hollow holds to y9,
    # one over the level 8, under the margin 2.
    H = bowl(rim=9)
    W, _ = A.replay(POND, H, 0)
    rep = A.Report()
    A.check_pond(W, A.water_cells(W), H, SDOC, rep)
    assert any("holds water only to y9" in f for f in rep.findings)


# ------------------------------------------------------------------------------------------------- alphas, synthetic
@pytest.fixture
def fake_jar(tmp_path):
    """aaa -> bbb at 20 -> ccc at 40; ddd alone; ggg -> hhh by trade; nnn not implemented."""
    p = tmp_path / "jar.jar"
    sp = {"aaa": {"evolutions": [{"variant": "level_up", "result": "bbb", "requirements": [{"variant": "level", "minLevel": 20}]}]},
          "bbb": {"evolutions": [{"variant": "level_up", "result": "ccc", "requirements": [{"variant": "level", "minLevel": 40}]}]},
          "ccc": {"evolutions": []}, "ddd": {"evolutions": []}, "hhh": {"evolutions": []},
          "ggg": {"evolutions": [{"variant": "trade", "result": "hhh", "requirements": []}]},
          "nnn": {"implemented": False, "evolutions": []}}
    with zipfile.ZipFile(p, "w") as z:
        for k, v in sp.items():
            z.writestr("data/cobblemon/species/generation9/%s.json" % k, json.dumps(v))
    return A.Jar(p)


REGIONS = {"subregions": [{"id": "hill", "polygons": [[[0, 0], [100, 0], [100, 100], [0, 100]]]}]}
DESIGN = {"rules": {"tiers": {"3": {"cap": 30}}, "hearts": {"next_cap": {"3": 35}}}}
WARD = {"id": "scar_tarn_t_ward", "pool": "cobblers:p", "position": {"x": 50, "y": 1, "z": 50}}


def alpha_findings(entries, jar, wards=(WARD,)):
    spawns = {"subregions": [{"id": "hill", "level_band": {"tier": 3}}],
              "entries": [dict(e, scope="p") for e in entries], "habitats": []}
    rep = A.Report()
    A.check_alphas(list(wards), spawns, REGIONS, DESIGN, jar, rep)
    return rep


@pytest.mark.parametrize("entry,expect", [
    ({"species": "bbb", "level": "18-30", "modifiers": "alpha=true"}, "under the level 20 aaa evolves into it at"),
    ({"species": "bbb", "level": "25-40", "modifiers": "alpha=true"}, "at or past its own evolution level 40"),
    ({"species": "ddd", "level": "33-30", "modifiers": "alpha=true"}, "is not [low, high]"),
    ({"species": "ddd", "level": "30-36", "modifiers": "alpha=true"}, "over tier 3's next cap 35"),
    ({"species": "ddd", "level": "30-33", "modifiers": "shiny=true"}, "carry no alpha=true"),
    ({"species": "zzz", "level": "30-33", "modifiers": "alpha=true"}, "no species file"),
    ({"species": "nnn", "level": "30-33", "modifiers": "alpha=true"}, "not implemented"),
])
def test_each_alpha_rule_names_its_own_fault(fake_jar, entry, expect):
    # removing this lets an alpha spawn under its evolution level, past the next cap, without its alpha flag, or as a
    # species the jar does not have.
    rep = alpha_findings([entry], fake_jar)
    assert any(expect in f for f in rep.findings), rep.findings


def test_a_clean_alpha_over_the_cap_but_under_the_next_is_a_note(fake_jar):
    # removing this turns the presence rule (above the cap only to the next leg's cap) into a failure. ddd 30-33 against
    # cap 30: 31, 32, 33 are over it, 3 levels.
    rep = alpha_findings([{"species": "ddd", "level": "30-33", "modifiers": "level=1 alpha=true"},
                          {"species": "hhh", "level": "29-30", "modifiers": "is_alpha=true"}], fake_jar)
    assert rep.findings == []
    assert any("3 level(s) over tier 3's cap 30" in n for n in rep.notes)


def test_a_ward_outside_every_tiered_subregion_and_an_empty_pool_fail(fake_jar):
    # removing this lets a pool with no entries, or a ward in no sub-region, pass with nothing checked.
    far = dict(WARD, position={"x": 500, "y": 1, "z": 500})
    assert any("not exactly one tier" in f for f in alpha_findings([{"species": "ddd", "level": "30-33", "modifiers": "alpha=true"}],
                                                                   fake_jar, wards=(far,)).findings)
    assert any("has no entry" in f for f in alpha_findings([], fake_jar).findings)


# ------------------------------------------------------------------------------------------------ overlaps, synthetic
def test_the_overlap_sweep_names_points_lines_and_boxes_and_skips_our_own(tmp_path):
    # removing this lets another file's thing under the growth go unnamed (our list is not the world). Written columns
    # x100..110 at z200. A point at (105, 205) is 5 away; a line through (105, 190)-(105, 210) crosses; a box holds
    # 6 columns (x105..110); a point 30 away and our own scar_tarn record are not named.
    for name, d in {"a.json": {"things": [{"id": "x", "x": 105, "z": 205}, {"id": "far", "x": 105, "z": 230},
                                          {"id": "scar_tarn_own", "x": 101, "z": 200}]},
                    "b.json": {"lot": {"min_x": 105, "min_z": 195, "max_x": 120, "max_z": 205}},
                    "c.json": {"road": [[105, 190], [105, 210]]}}.items():
        (tmp_path / name).write_text(json.dumps(d), encoding="utf-8")
    cols = [(x, 200) for x in range(100, 111)]
    rep = A.Report()
    A.check_overlaps(cols, SDOC, rep, data_dir=tmp_path)
    text = "\n".join(rep.findings)
    assert "(105, 205) is 5 block(s)" in text
    assert "c.json.road, a line, passes 0 block(s)" in text
    assert "holds 6 written column(s)" in text
    assert "105, 230" not in text and "scar_tarn_own" not in text and len(rep.findings) == 3


# --------------------------------------------------------------------------------------------------------- the real
@pytest.fixture(scope="module")
def H():
    import terrain as T
    try:
        return A.heights_from_heightmap(A.audit_window(DOC))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


RUNNER = ("import sys\nsrc, real = sys.argv[1], sys.argv[2]\nsys.argv = [real] + sys.argv[3:]\n"
          "exec(compile(open(src, encoding='utf-8').read(), real, 'exec'), {'__name__': '__main__', '__file__': real})\n")


def run_generator(tmp_path, args, mutations=()):
    """The generator's CLI on its own source with each (old, new) text replaced; data/ untouched."""
    src = GEN.read_text(encoding="utf-8")
    for old, new in mutations:
        assert src.count(old) >= 1, "the mutation no longer matches tools/scar_tarn.py: %r" % old
        src = src.replace(old, new)
    p = tmp_path / "scar_tarn_mutant.py"
    p.write_text(src, encoding="utf-8")
    r = subprocess.run([sys.executable, "-c", RUNNER, str(p), str(GEN)] + list(args), capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout + r.stderr)[-600:]
    return r.stdout


def built_functions(tmp_path, mutations=()):
    """{function name: lines} the mutated generator's CLI writes (build, then each arm)."""
    out = tmp_path / "pack"
    run_generator(tmp_path, ["build", "--out", str(out)], mutations)
    return A.read_functions(out)


def built_lines(tmp_path, mutations=()):
    """The tarn's own function only (the water checks: no arm writes water), as the audit's original tests ran it."""
    return built_functions(tmp_path, mutations)["build"]


def water_findings(lines, H):
    rep = A.Report()
    st = A.check_water(lines, H, DOC, rep)
    return rep, st


@pytest.fixture(scope="module")
def baseline(H, tmp_path_factory):
    return built_lines(tmp_path_factory.mktemp("base"))


def test_the_built_tarn_holds_its_water_at_drop_0_and_1_and_nothing_escapes_at_2(H, baseline):
    # removing this loses the one check that replays the pack the server runs over the ground it runs on.
    rep, st = water_findings(baseline, H)
    assert rep.findings == []
    assert st[0]["open_faces"] == 0 and st[1]["open_faces"] == 0
    assert not st[2]["escaped"] and st[2]["falls"] == 0


def test_the_built_tarn_clears_every_authored_thing_the_pad_and_the_paths(H, baseline):
    # removing this lets the tarn's own growth spread over another place's record or the Scar's avenue unseen.
    rep = A.Report()
    cols = A.written_columns(baseline, H)
    A.check_overlaps(cols, DOC, rep)
    A.check_paths(cols, DOC, rep)
    assert rep.findings == []


@pytest.fixture(scope="module")
def baseline_functions(H, tmp_path_factory):
    return built_functions(tmp_path_factory.mktemp("basefn"))


def test_the_built_wood_passes_every_forest_rule_and_every_arm_has_trees(H, baseline_functions):
    # removing this loses the one check of the arms against the ground, the outline, the Scar, Thundurus and the limits.
    rep = A.Report()
    stats = A.check_forest(baseline_functions, H, DOC, rep)
    assert rep.findings == []
    assert sorted(stats) == sorted("arm_" + lb["id"] for lb in DOC["growth"]["arms"]["lobes"])
    assert all(v["trunks"] > 20 for v in stats.values()), stats


def test_the_whole_pack_overlaps_the_authored_things_and_the_pad_only_where_the_arms_are_allowed(H, baseline_functions):
    # removing this lets the arms spread over another record's thing or the tarn's own function over the pad. The arms are
    # exempt from the pad's radius rule on purpose (check_forest holds them to the city's own geometry); the tarn is not.
    rep = A.Report()
    lines = [l for ls in baseline_functions.values() for l in ls]
    cols = A.written_columns(lines, H)
    A.check_overlaps(cols, DOC, rep)
    A.check_paths(cols, DOC, rep, pad_cols=A.written_columns(baseline_functions["build"], H))
    assert rep.findings == []
    rep2 = A.Report()
    A.check_paths(cols, DOC, rep2)          # without the exemption the arms are on the pad and the rule says so
    assert any("inside the pad's radius" in f for f in rep2.findings), rep2.findings


def test_the_shipped_wards_and_pools_pass(H, baseline):
    # removing this lets the four Habitat Blocks or their pools drift from the pack and the rules.
    jp = A.find_jar()
    if jp is None:
        pytest.skip("the Cobblemon 1.8.0 jar snapshot is not on this machine")
    wards = A.tarn_wards(json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"])
    assert len(wards) == 4
    rep = A.Report()
    A.check_wards(baseline, H, wards, rep)
    A.check_alphas(wards, json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8")),
                   json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8")),
                   json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8")), A.Jar(jp), rep)
    assert rep.findings == []


# ------------------------------------------------------------------------------------------------ generator mutations
WATER_UP = ("        for y in range(g + 1, yS + 1):\n            plan.put(\"water\", x, y, z, WATER)",
            "        for y in range(g + 1, yS + 2):\n            plan.put(\"water\", x, y, z, WATER)")
LEVEL_UP = [("    yS = P[\"water_level\"]\n    seed = tuple(P[\"seed\"])", "    yS = P[\"water_level\"] + 1\n    seed = tuple(P[\"seed\"])"),
            ("    spill, spilled = flood(plan, seed, yS + 2)", "    spill, spilled = flood(plan, seed, yS + 1)")]
ONE_LIFT = [("    lifted = 0\n", "    lifted = 0\n    _skip = min(c for c in ring4 if plan.gr(*c) < lift)\n"),
            ("        if g < lift:\n", "        if g < lift and (x, z) != _skip:\n")]
NO_RIM = [("        if g < lift:\n", "        if False:\n"),
          ("        else:\n            plan.put(\"bank\", x, g, z, \"minecraft:\" + top)", "        else:\n            pass"),
          ("    for drop in (0, 1):\n        leaks = containment(pl, drop)", "    for drop in ():\n        leaks = containment(pl, drop)")]
TREE_IN_WATER = [("    # trees\n    for (x, z) in cands:", "    place_tree(plan, \"spruce\", P[\"seed\"][0], P[\"seed\"][1], 12)\n"
                  "    # trees\n    for (x, z) in cands:")]


@pytest.mark.parametrize("mutations,expect", [
    ([WATER_UP], "water block(s) over the level y237"),
    (LEVEL_UP, "water block(s) over the level y237"),
    (ONE_LIFT, "1 rim column(s)"),
    (NO_RIM, "drop 1: "),
    (TREE_IN_WATER, "cell(s) of the pond are not water"),
], ids=["water_one_higher", "level_one_higher_guard_widened", "one_rim_lift_removed", "rim_and_guard_removed",
        "tree_in_the_water"])
def test_a_mutated_generator_is_caught(H, tmp_path, mutations, expect):
    # removing this leaves the audit unproven against the code it audits: each mutation edits tools/scar_tarn.py's
    # text only, so a check sharing the generator's derivation would move with it and pass.
    rep, _st = water_findings(built_lines(tmp_path, mutations), H)
    assert any(expect in f for f in rep.findings), rep.findings


@pytest.mark.parametrize("mutation,expect", [
    (("\"level\": \"%d-%d\" % (lo, hi)", "\"level\": \"%d-%d\" % (lo, hi + 3)"), "over tier 3's next cap 35"),
    (("    lo, hi = A[\"band\"]\n", "    lo, hi = 22, A[\"band\"][1]\n"), "under the level 27 chinchou evolves into it at"),
    (("\"modifiers\": A[\"modifiers\"]", "\"modifiers\": \"\""), "carry no alpha=true"),
], ids=["alpha_over_the_next_cap", "alpha_under_its_evolution", "alpha_flag_dropped"])
def test_a_mutated_generator_writes_records_the_alpha_check_rejects(H, tmp_path, mutation, expect):
    # removing this lets the generator's records drift past the cap or lose the alpha flag with nothing to say so.
    jp = A.find_jar()
    if jp is None:
        pytest.skip("the Cobblemon 1.8.0 jar snapshot is not on this machine")
    out = run_generator(tmp_path, ["records"], [mutation])
    f = tmp_path / "records.json"
    f.write_text(out, encoding="utf-8")
    wards, spawns = A.records_inputs(f)
    spawns["subregions"] = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))["subregions"]
    rep = A.Report()
    A.check_alphas(wards, spawns, json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8")),
                   json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8")), A.Jar(jp), rep)
    assert any(expect in f for f in rep.findings), rep.findings


def test_the_unmutated_records_pass_the_alpha_check(tmp_path):
    # removing this makes the mutation tests above meaningless: a check that fails the clean records proves nothing.
    jp = A.find_jar()
    if jp is None:
        pytest.skip("the Cobblemon 1.8.0 jar snapshot is not on this machine")
    f = tmp_path / "records.json"
    f.write_text(run_generator(tmp_path, ["records"]), encoding="utf-8")
    wards, spawns = A.records_inputs(f)
    spawns["subregions"] = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))["subregions"]
    rep = A.Report()
    A.check_alphas(wards, spawns, json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8")),
                   json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8")), A.Jar(jp), rep)
    assert rep.findings == []


# ------------------------------------------------------------------------------------------------ the forest, synthetic
def test_the_hull_the_polygon_test_and_the_log_columns_on_hand_computed_input():
    # removing this leaves the forest rules' geometry unproven on input whose answer is known without running anything.
    # hull of a 10 x 10 square's corners with an interior point is the four corners; (5, 5) is inside, (11, 5) is not,
    # and a cell centre (x + .5) of column 9 is inside while column 10's is not (the square spans 0..10).
    sq = A.hull([(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)])
    assert sorted(sq) == [(0, 0), (0, 10), (10, 0), (10, 10)]
    got = A.inside_polygon(np.array([[5, 5], [11, 5], [9, 9], [10, 5]], float), sq)
    assert got.tolist() == [True, False, True, False]
    assert A.ring_inside(5.5, 5.5, sq) and not A.ring_inside(10.5, 5.5, sq)
    lines = ["setblock 4 70 5 minecraft:spruce_log[axis=y]", "fill 7 71 8 7 74 8 minecraft:birch_log[axis=y]",
             "setblock 9 70 9 minecraft:spruce_log[axis=x]", "fill 1 70 1 3 70 1 minecraft:mossy_cobblestone"]
    assert A.log_columns(lines) == {(4, 5): 70, (7, 8): 71}


def test_read_function_runs_build_first_then_each_arm_in_name_order(tmp_path):
    # removing this lets the audit replay the arms before the pond they stand round, or skip one.
    d = tmp_path / "data" / "cobblers" / "function" / "scar_tarn"
    d.mkdir(parents=True)
    for n in ("arm_b", "build", "arm_a"):
        (d / (n + ".mcfunction")).write_text("# %s\nsetblock 0 0 0 minecraft:stone\n" % n, encoding="utf-8")
    fns = A.read_functions(tmp_path)
    assert list(fns) == ["build", "arm_a", "arm_b"]
    assert [l for l in A.read_function(tmp_path) if l.startswith("#")] == ["# build", "# arm_a", "# arm_b"]
    assert A.read_functions(tmp_path / "nowhere") is None


# --------------------------------------------------------------------------------------- the forest, generator mutations
AVOID_OFF = [("    for ab in AR[\"avoid_boxes\"]:", "    for ab in []:")]
# the points net AND the generator's own fail-closed guard over the same points (authored_sweep): the guard would otherwise
# refuse to build the mutant and the audit would never see it
POINTS_OFF = [("        mask |= np.hypot(xx - px, zz - pz) < m + 1.5", "        mask |= np.hypot(xx - px, zz - pz) < 0.5"),
              ("    probs += authored_sweep(pl)\n    return probs", "    return probs")]
CORE_OFF = [("    if core:\n        mask |= polygon_mask(", "    if False:\n        mask |= polygon_mask(")]
RELIEF_OFF = [("            if R3[iz, ix] > rmax_relief:", "            if False:")]
STREETS_OFF = [("            mask |= seg_dist_grid(xx, zz, a, b) < m + 0.5", "            mask |= seg_dist_grid(xx, zz, a, b) < 1.5")]
OUTLINE_OFF = STREETS_OFF + [("    mask |= ~polygon_mask(xx + 0.5, zz + 0.5, ring)", "    pass")]
# Thundurus is held by two nets that overlap (the avoid box, and the 24-block circles round its portal, chamber and spawn-free
# box), so one net removed changes nothing and proves nothing: the mutation removes both. The city likewise (the 24-block
# line sweep, the 24-block circles round its x/z points, the core hull).
THUNDURUS_OFF = AVOID_OFF + POINTS_OFF
CITY_OFF = POINTS_OFF + STREETS_OFF + CORE_OFF


@pytest.mark.parametrize("mutations,expect", [
    (THUNDURUS_OFF, "Thundurus's spawn-free box"),
    (CORE_OFF, "inside the city's core"),
    (RELIEF_OFF, "arm trunk(s) on ground steeper"),
    (CITY_OFF, "from the Scar's"),
    (CITY_OFF, "inside the city's core"),
    (CITY_OFF, "a ruin at"),
    (OUTLINE_OFF, "outside the mt_vessu outline"),
], ids=["thundurus_nets_removed", "city_core_removed", "slope_limit_removed", "city_nets_removed_street",
        "city_nets_removed_core", "city_nets_removed_ruin", "outline_nets_removed"])
def test_a_mutated_generator_is_caught_by_the_forest_rules(H, tmp_path, mutations, expect):
    # removing this leaves the forest rules unproven against the code they audit: each mutation edits tools/scar_tarn.py's
    # text only (data/scar_tarn.json untouched), so a rule that shared the generator's derivation would move with it and pass.
    # The baseline run is clean (test above), so the finding is the mutation's. Each lobe is drawn wide enough to reach what
    # the removed net protects, which is why removing the net puts a tree there.
    fns = built_functions(tmp_path, mutations)
    rep = A.Report()
    A.check_forest(fns, H, DOC, rep)
    assert any(expect in f for f in rep.findings), (expect, rep.findings[:4])
