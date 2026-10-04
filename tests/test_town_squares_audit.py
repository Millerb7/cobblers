"""tools/town_squares_audit.py: the town squares (R13) and their traders (R17M), audited independently.

Two kinds of test. The synthetic ones feed the audit's pieces hand-built inputs whose answers can be worked out on
paper (a row of cells and one lantern; a three-command function; a corridor with a wall; a two-counter market), so
the audit is tested on surfaces other than the real towns. The real ones run it over the committed data and the
built R13 functions; they skip, naming the command, when build/ or derived/ has not been produced. The mutation
tests change the GENERATORS (tools/plaza_centre.py, tools/markets.py) with the data untouched, and require the audit
to see what the builders' own checks do not.

Not covered here (runtime): an NPC spawning, staying and facing; a purchase; real light and pathfinding.
"""
from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import town_squares_audit as A  # noqa: E402

BUILT = (A.FUNC_DIR / "index.txt").is_file()
PLANS = all((A.PLAN_DIR / ("%s_plan.json" % t)).is_file()
            for t in A.load(ROOT / "data" / "plaza_centres.json")["towns"] if t != "hometown")


def _heightmap():
    """'' when the canonical heightmap loads, else why not (the skip reason names it)."""
    import ground
    try:
        ground.Ground()
    except (SystemExit, OSError) as e:          # no source root, or the pinned file is absent
        return "the heightmap: %s" % e
    return ""


NO_HEIGHTMAP = _heightmap()
HEIGHTMAP = not NO_HEIGHTMAP
need_build = pytest.mark.skipif(not (BUILT and PLANS and HEIGHTMAP),
                                reason="needs build/datapacks/cobblers_plaza_centres (python tools/plaza_centre.py "
                                       "build), derived/towns/*_plan.json (python tools/town_plan.py <town>) and %s"
                                       % (NO_HEIGHTMAP or "the heightmap"))


class FlatGeo:
    """A town that is a flat floor at y0 with a given rect and street set: for hand-computable cases."""

    def __init__(self, rect, y=0, street=(), sea=-100):
        self.rect, self.y, self.street, self.sea = rect, y, set(street), sea
        self.footprints, self.lamps, self.lots, self.anchors, self.sign = {}, [], [], [], None
        self.plan, self.plan_missing, self.planned = {}, False, False

    def floor(self, x, z):
        return self.y


# ----------------------------------------------------------------------------------------- the voxel model, by hand
def test_voxelise_applies_fill_then_setblock_in_order_and_reads_sign_nbt():
    # Without it the audit would read a function differently from the server, and every built-result check lies.
    lines = ["# a comment", "forceload add 0 0 15 15",
             "fill 0 1 0 0 3 0 minecraft:air replace #minecraft:replaceable",
             "setblock 0 1 0 minecraft:oak_fence",
             "fill 0 1 0 0 3 0 minecraft:air replace #minecraft:replaceable",
             "setblock 1 1 0 minecraft:oak_wall_sign[facing=west]{front_text:{messages:['\"A b\"','\"c\"']}}"]
    model, problems = A.voxelise(lines)
    assert problems == []
    assert model[(0, 1, 0)] == "minecraft:oak_fence"          # a replace-replaceable fill keeps a solid block
    assert model[(0, 2, 0)] == model[(0, 3, 0)] == "minecraft:air"
    assert A.name_of(model[(1, 1, 0)]) == "minecraft:oak_wall_sign"


def test_voxelise_names_a_command_it_cannot_model():
    # Without it a clone or an execute in the function would be silently skipped, and its blocks never audited.
    _m, problems = A.voxelise(["clone 0 0 0 1 1 1 5 5 5"])
    assert len(problems) == 1 and "does not know" in problems[0]


# --------------------------------------------------------------------------------------------------- light, by hand
def test_light_rule_one_lantern_on_a_row_of_31_cells_leaves_16_dark():
    # Without it the light rule could drift (reach, threshold, the standing block) and no number would show it.
    # A lantern (15) at (0, 1, 0), floor y0, so standing y1: cell x has level 15 - x, lit iff x <= 14 -> 16 dark.
    geo = FlatGeo((0, 0, 30, 0))
    P, n = A.light_checks("t", geo, {(0, 1, 0): "minecraft:lantern[hanging=false]"}, set())
    assert n == 1 and len(P) == 1 and "16 square cell" in P[0][2]
    # an end rod emits 14, not 15: one more dark cell; the generator's model treats both as 15
    P, _n = A.light_checks("t", geo, {(0, 1, 0): "minecraft:end_rod"}, set())
    assert "17 square cell" in P[0][2]
    # a street cell over the square is counted separately, never skipped
    geo = FlatGeo((0, 0, 30, 0), street={(30, 0)})
    P, _n = A.light_checks("t", geo, {(0, 1, 0): "minecraft:lantern"}, set())
    assert sorted(p[1] for p in P) == ["t", "t:street"]


# ------------------------------------------------------------------------------------------------- stalls, by hand
def _stall_model():
    # a counter at (5, 1, 5), customers to the south, the keeper at (5, 1, 4): feet and head cleared, floor at y0
    return {(5, 1, 5): "minecraft:stripped_oak_log[axis=x]", (5, 1, 4): "minecraft:air", (5, 2, 4): "minecraft:air"}


STALL = {"id": "t_stall_1", "at": [5, 1, 5], "facing": "south", "keeper_at": [5, 1, 4, 0], "sells": "fish"}


def test_stall_checks_pass_a_good_stall_and_name_each_fault():
    # Without it a keeper inside a post, on no floor, or with its back to the counter would pass.
    geo = FlatGeo((0, 0, 10, 10))
    assert A.stall_checks("t", {"stalls": [STALL]}, geo, _stall_model()) == []
    m = _stall_model()
    del m[(5, 1, 5)]
    assert [p[1] for p in A.stall_checks("t", {"stalls": [STALL]}, geo, m)] == ["t_stall_1:counter"]
    m = _stall_model()
    m[(5, 2, 4)] = "minecraft:oak_slab[type=bottom]"
    assert [p[1] for p in A.stall_checks("t", {"stalls": [STALL]}, geo, m)] == ["t_stall_1:air1"]
    bad_yaw = dict(STALL, keeper_at=[5, 1, 4, 180])          # yaw 180 looks north, away from the counter
    assert [p[1] for p in A.stall_checks("t", {"stalls": [bad_yaw]}, geo, _stall_model())] == ["t_stall_1:yaw"]
    assert [p[1] for p in A.stall_checks("t", {"stalls": [STALL]}, FlatGeo((0, 0, 10, 10), y=-3), _stall_model())] \
        == ["t_stall_1:floor"]


def test_yaw_convention_is_minecrafts():
    # Without it every keeper could face the wrong way and the yaw check would agree with it.
    for yaw, want in ((0, (0, 1)), (90, (-1, 0)), (180, (0, -1)), (-90, (1, 0))):
        vx, vz = A.yaw_vec(yaw)
        assert (round(vx), round(vz)) == want


# ------------------------------------------------------------------------------------------------ walking, by hand
def test_walk_goes_round_a_wall_and_not_up_a_cliff():
    # Without it a square walled off from its Centre, or reached only up a two-block step, would pass.
    geo = FlatGeo((0, 0, 4, 4))
    wall = {(2, z) for z in range(0, 4)}                      # a wall with a gap at z=4
    seen = A.walk(geo, [(0, 0)], wall, (0, 0, 4, 4))
    assert seen[(4, 0)] == 4 + 2 * 4                          # down to z=4, across, back up
    wall = {(2, z) for z in range(0, 5)}
    assert (4, 0) not in A.walk(geo, [(0, 0)], wall, (0, 0, 4, 4))

    class Cliff(FlatGeo):
        def floor(self, x, z):
            return 0 if x < 2 else 2
    assert (3, 0) not in A.walk(Cliff((0, 0, 4, 0)), [(0, 0)], set(), (0, 0, 4, 0))


def test_door_starts_are_the_middle_half_outside_the_facing_edge():
    # Without it a door could be credited from a corner of the building that the square happens to touch.
    assert A.door_starts((10, 10, 17, 13), "south") == [(x, 14) for x in range(11, 17)]
    assert A.door_starts((10, 10, 17, 13), "west") == [(9, 10), (9, 11), (9, 12), (9, 13)]


# ------------------------------------------------------------------------------------------- markets, by hand
def _market(stock_counter, stock_stall, badge=1):
    return {"income_basis": {"cumulative_by_badge": {str(b): 1000 * b for b in range(1, 9)}, "target_ratio": 0.7},
            "counters": [{"id": "c", "town": "gym1_town", "badge": badge, "status": "sited", "stock": stock_counter}],
            "stalls": [{"id": "s", "town": "gym1_town", "badge": badge, "status": "sited", "sells": "fish",
                        "stock": stock_stall}]}


TOWNS = {"towns": [{"id": "gym1_town", "critical_path": True}, {"id": "sea_town", "critical_path": False}]}


def test_curve_counts_counters_and_only_a_stalls_gated_lines():
    # Without it a stall line could move the money curve unseen, or a pick-one group be counted in full.
    counter = [{"id": "a", "item": "x:a", "price": 300, "gate": "gym1_cleared"},
               {"id": "b", "item": "x:b", "price": 200, "group": "g", "gate": "gym1_cleared"},
               {"id": "c", "item": "x:c", "price": 500, "group": "g", "gate": "gym1_cleared"},
               {"id": "d", "item": "x:d", "price": 9000, "stretch": True}]
    stall = [{"id": "e", "item": "minecraft:cod", "price": 100, "gate": None},
             {"id": "f", "item": "minecraft:salmon", "price": 40, "gate": "gym1_cleared"}]
    rows = A.curve(_market(counter, stall), TOWNS)
    assert rows[0] == (1, 300 + 500 + 40, 1000, 0.84)          # a, g at its dearest, f; not d, not e
    assert rows[7][1] == 840                                   # nothing after badge 1


def test_power_rule_flags_an_ungated_ball_and_passes_a_badge_gated_one():
    # Without it a stall could sell Ultra Balls from the first visit.
    doc = _market([{"id": "u", "item": "cobblemon:ultra_ball", "price": 1, "gate": "gym6_cleared"}],
                  [{"id": "b", "item": "cobblemon:great_ball", "price": 1, "gate": None},
                   {"id": "k", "item": "minecraft:dried_kelp", "price": 1, "gate": None},
                   {"id": "p", "item": "minecraft:splash_potion", "price": 1, "gate": None}])
    P, _u = A.item_checks(doc, set(), {})
    assert sorted(p[1] for p in P if p[0] == "power") == ["s:cobblemon:great_ball", "s:minecraft:splash_potion"]


def test_item_rule_reads_the_block_an_item_puts_down_and_what_it_grows():
    # Without it a seed whose stem fruits into a spawn block (a pumpkin) would be sold as harmless.
    doc = _market([], [{"id": "p", "item": "minecraft:pumpkin_seeds", "price": 1, "gate": None}])
    P, _u = A.item_checks(doc, {"minecraft:pumpkin"}, {"minecraft": {"pumpkin_seeds"}})
    assert [p[1] for p in P] == ["s:minecraft:pumpkin_seeds:spawn"]
    P, _u = A.item_checks(doc, set(), {"minecraft": set()})
    assert [p[1] for p in P] == ["s:minecraft:pumpkin_seeds:exists"]


def test_staffing_names_an_unstaffed_stall_a_double_and_a_stray_keeper():
    # Without it a stall could stand empty, or two keepers share one spot, or a keeper stand off every stall.
    plazas = {"towns": {"t": {"stalls": [dict(STALL), dict(STALL, id="t_stall_2", keeper_at=[9, 1, 9, 0])]}}}
    mk = {"counters": [{"id": "a", "town": "t"}, {"id": "b", "town": "t"}],
          "stalls": [{"id": "c", "town": "t", "sells": "fish"}, {"id": "d", "town": "northlight"}]}
    npcs = [("cobblers:npc_market_a", (5, 1, 4), 0), ("cobblers:npc_market_b", (5, 1, 4), 0),
            ("cobblers:npc_stall_c", (1, 1, 1), 0), ("cobblers:npc_stall_d", (2, 2, 2), 0)]
    keys = sorted(p[1] for p in A.staff_checks(plazas, mk, npcs))
    assert keys == ["cobblers:npc_stall_c:seat", "t_stall_1", "t_stall_2"]


def test_every_stall_keepers_theme_word_has_a_vocabulary():
    # Without it a new stall theme would fail every line without anyone having written its words.
    # (Counters are not judged by vocabulary: their stock is the badge ladder, seated by stall_why.)
    mk = A.load(ROOT / "data" / "markets.json")
    assert {s.get("sells") for s in mk["stalls"]} - set(A.THEME_WORDS) == set()


def test_the_survey_still_names_the_towns_with_nowhere_to_spend():
    # Without it SURVEY_NO_SPEND could drift from the document it claims to read.
    text = A.SURVEY.read_text(encoding="utf-8")
    sec = text[text.index("Places where a player can spend nothing"):text.index("## 1.")]
    for label in A.SURVEY_NO_SPEND:
        assert label in sec, label


def test_curve_is_unchanged_by_the_stalls_and_inside_the_target():
    # Without it a gated stall line could take the critical path over 0.70 of income, or quietly move the ladder.
    mk = A.load(ROOT / "data" / "markets.json")
    towns = A.load(ROOT / "data" / "towns.json")
    rows = A.curve(mk, towns)
    assert [(b, a, i) for b, a, i, _r in rows] == A.BASELINE_CURVE
    assert all(0.65 <= r <= 0.70 for _b, _a, _i, r in rows), rows
    no_stalls = dict(mk, stalls=[])
    assert A.curve(no_stalls, towns) == rows


def test_wired_into_prepare_after_the_squares_and_the_markets():
    # Without it the audit exists and never runs: the failure CLAUDE.md "A success report is not the work" names.
    import reapply
    jobs = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="x", server_dir="x"))]
    i = jobs.index("town_squares_audit")
    assert jobs.index("plaza_centre:build") < i and jobs.index("markets:build") < i
    assert jobs.index("markets:audit_independent") < i


def test_audit_reads_no_world_and_no_builder_helper_for_expectations():
    # Without it the audit could quietly start sharing the builders' derivation, which is what makes it worthless.
    import re
    src = (ROOT / "tools" / "town_squares_audit.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    code = code[code.index('"""', code.index('"""') + 3) + 3:]          # past the module docstring
    assert not re.search(r"^\s*(import|from)\s+plaza_centre\b", code, re.M)
    for helper in ("position", "curve", "priced", "contract_keeper", "load_plazas", "stall_problems", "keepers"):
        assert "markets.%s(" % helper not in code, helper
    assert ".mca" not in code and "--world" not in code


# ------------------------------------------------------------------------------------------------- the real towns
@pytest.fixture(scope="module")
def real():
    if not (BUILT and PLANS and HEIGHTMAP):
        pytest.skip("needs the built R13 pack, the town plans and the heightmap")
    return A.audit(None, str(A.DEFAULT_JAR_DIR), str(A.DEFAULT_VANILLA))


@need_build
def test_the_squares_and_their_traders_have_no_unknown_problem(real):
    # Without it a square on a street, a dark corner, an unstaffed stall or an off-theme line would ship.
    assert real["problems"] == [], "\n".join(m for _c, _k, m in real["problems"][:20])


@need_build
def test_known_defects_are_exactly_the_recorded_ones(real):
    # Strict, like a strict xfail: a new defect fails above; a FIXED one fails here until KNOWN is trimmed.
    assert real["known_fixed"] == []
    assert {(c, k) for c, k, _m in real["known"]} == set(A.KNOWN)


@need_build
def test_every_town_reaches_its_square_from_both_doors(real):
    # Without it a town whose Centre opens onto a cliff would be counted as having a middle.
    for t, r in real["towns"].items():
        assert set(r["reach"]) == {"pokecenter", "pokemart"}, t
        assert r["stalls"] >= 1 and r["blocks"] > 0, t


# --------------------------------------------------------------------------------------- mutating the generators
def _build_into(tmp_path, monkeypatch):
    import plaza_centre as P
    pack = tmp_path / "pack"
    monkeypatch.setattr(P, "PACK", pack)
    monkeypatch.setattr(P, "FUNCS", pack / "data" / "cobblers" / "function" / "plaza_centres")
    monkeypatch.setattr(P, "REPORT", tmp_path / "report")
    P.build(types.SimpleNamespace(source_root=None))         # the builder's own checks must PASS the mutation
    monkeypatch.setattr(A, "FUNC_DIR", pack / "data" / "cobblers" / "function" / "plaza_centres")
    return P


def _npcs():
    import markets
    doc = markets.load()
    return [(a[2], tuple(a[1]), a[3]) for a in markets.npc_placements(doc) + markets.stall_placements(doc)]


@need_build
def test_mutation_a_stall_built_without_its_counter_is_caught(tmp_path, monkeypatch, capsys):
    # Without it the audit could be reading the record instead of the blocks, and agree with a stall that has no front.
    import plaza_centre as P
    orig = P.piece_stall

    def no_counter(town, spec, goods):
        p = orig(town, spec, goods)
        p.blocks = [b for b in p.blocks if (b[0], b[1], b[2]) != (0, 0, 0)]
        return p
    monkeypatch.setitem(P.PIECES, "stall", no_counter)
    _build_into(tmp_path, monkeypatch)
    res = A.audit(None, None, None, npcs=_npcs())
    caught = {k for c, k, _m in res["problems"] if c == "stall" and k.endswith(":counter")}
    n = sum(len(t["stalls"]) for t in A.load(ROOT / "data" / "plaza_centres.json")["towns"].values())
    assert len(caught) == n == 43


@need_build
def test_mutation_lanterns_swapped_for_chains_that_the_builder_counts_as_light_is_caught(tmp_path, monkeypatch):
    # Without it the light check would share the generator's idea of what a light is, and pass a dark square.
    import plaza_centre as P
    orig_lamp, orig_stall, orig_lights = P.piece_lamp_post, P.piece_stall, P.lights_of

    def chains(fn):
        def piece(town, spec, goods):
            p = fn(town, spec, goods)
            p.blocks = [(x, dy, z, "minecraft:chain[axis=y]" if "lantern" in s else s) for x, dy, z, s in p.blocks]
            return p
        return piece
    monkeypatch.setitem(P.PIECES, "lamp_post", chains(orig_lamp))
    monkeypatch.setitem(P.PIECES, "stall", chains(orig_stall))
    monkeypatch.setattr(P, "lights_of", lambda blocks: orig_lights(blocks) + [
        (x, y, z) for x, y, z, s in blocks if s.startswith("minecraft:chain")])
    _build_into(tmp_path, monkeypatch)
    res = A.audit(None, None, None, npcs=_npcs())
    dark = {k for c, k, _m in res["problems"] if c == "light"}
    assert len(dark) >= 3, dark


@need_build
def test_mutation_markets_seating_shifted_one_block_is_caught(monkeypatch):
    # Without it a keeper standing inside a stall's post, or in front of the counter, would be reported as staffed.
    import markets
    orig = markets.position

    def shifted(rec, plazas):
        at, yaw, src = orig(rec, plazas)
        return ([at[0] + 1, at[1], at[2]] if at else at), yaw, src
    monkeypatch.setattr(markets, "position", shifted)
    P = A.staff_checks(A.load(ROOT / "data" / "plaza_centres.json"), A.load(ROOT / "data" / "markets.json"), _npcs())
    unstaffed = {k for _c, k, _m in P if k.count("_stall_") == 1 and ":" not in k}
    assert len(unstaffed) == 43
