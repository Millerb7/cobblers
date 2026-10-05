"""tools/town_squares_audit.py: the town squares (R13) and their traders (R17M), audited independently.

Two kinds of test. The synthetic ones feed the audit's pieces hand-built inputs whose answers can be worked out on
paper (a row of cells and one lantern; a three-command function; a corridor with a wall; a two-counter market), so
the audit is tested on surfaces other than the real towns. The real ones run it over the committed data and the
built R13 functions; they skip, naming the command, when build/ or derived/ has not been produced. The mutation
tests change the GENERATORS (tools/plaza_centre.py, tools/markets.py) with the data untouched, and require the audit
to see what the builders' own checks do not.

Not covered here (runtime): an NPC or merchant spawning, staying and facing; a purchase through the merchant's
screen; the old dialogue keeper actually being removed; real light and pathfinding.
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
    # a tent's table at (5, 1, 5), customers to the south: the keeper in the open front at (5, 1, 6), feet and head
    # cleared, a lantern over the head at y3; the customer at (5, 1, 7); floor at y0
    return {(5, 1, 5): "minecraft:spruce_slab[type=top]", (5, 1, 6): "minecraft:air", (5, 2, 6): "minecraft:air",
            (5, 3, 6): "minecraft:lantern[hanging=true]"}


STALL = {"id": "t_stall_1", "at": [5, 1, 5], "facing": "south", "keeper_at": [5, 1, 6, 0], "sells": "fish"}


def test_stall_checks_pass_an_open_tent_and_name_each_fault():
    # Without it a keeper behind the table, inside a post, on no floor, turned to the table, or with a block between
    # it and the customer would pass (the owner, 2026-10-04: "the stalls all block the villager from access").
    geo = FlatGeo((0, 0, 10, 10))
    keys = lambda st, m, g=geo: [p[1] for p in A.stall_checks("t", {"stalls": [st]}, g, m)]
    assert keys(STALL, _stall_model()) == []
    m = _stall_model()
    del m[(5, 1, 5)]
    assert keys(STALL, m) == ["t_stall_1:counter"]
    m = _stall_model()
    m[(5, 2, 6)] = "minecraft:oak_slab[type=bottom]"
    assert keys(STALL, m) == ["t_stall_1:air1"]
    # yaw 180 looks north, at the table and away from the customers
    assert keys(dict(STALL, keeper_at=[5, 1, 6, 180]), _stall_model()) == ["t_stall_1:yaw"]
    assert keys(STALL, _stall_model(), FlatGeo((0, 0, 10, 10), y=-3)) == ["t_stall_1:floor", "t_stall_1:customer_floor"]
    # the old booth: keeper behind the table, facing it -- wrong side AND wrong way; its customer cell is the table
    m = _stall_model()
    m.update({(5, 1, 4): "minecraft:air", (5, 2, 4): "minecraft:air"})
    assert keys(dict(STALL, keeper_at=[5, 1, 4, 0]), m) == ["t_stall_1:front", "t_stall_1:customer0"]
    m = _stall_model()
    m[(5, 1, 7)] = "minecraft:spruce_fence"                   # a post between the customer and the keeper
    assert keys(STALL, m) == ["t_stall_1:customer0"]
    m = _stall_model()
    m[(5, 1, 7)] = "minecraft:red_carpet"                     # a carpet is walked over
    assert keys(STALL, m) == []


def test_the_customer_cell_is_two_steps_out_on_the_customers_side():
    # Without it the reach check would walk to the keeper's cell and call the stall served.
    for facing, want in (("south", (5, 7)), ("north", (5, 3)), ("east", (7, 5)), ("west", (3, 5))):
        assert A.customer_cell(dict(STALL, facing=facing)) == want


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


def _summon(stall_id, x, y, z, yaw=0.0, kind="cobbledollars:cobble_merchant", name="Fisher", shop=None):
    shop = shop or '[{Category:"Fish",Offers:[{Item:{count:1,id:"minecraft:cod"},Price:"20"}]}]'
    return ('summon %s %s.5 %s %s.5 {CustomName:"{\\"text\\": \\"%s\\"}",CobbleMerchantShop:%s,NoAI:1b,'
            'PersistenceRequired:1b,Rotation:[%sf,0.0f],Tags:["cobblers_stall","cobblers_stall_%s","cobblers_stall_new"]}'
            % (kind, x, y, z, name, shop, yaw, stall_id))


def _kill(x, y, z, r=2.5):
    return "execute if entity @e[tag=a] run kill @e[type=cobblemon:npc,x=%d.5,y=%d,z=%d.5,distance=..%s]" % (x, y, z, r)


MK = {"counters": [{"id": "a", "town": "t"}, {"id": "b", "town": "t"}],
      "stall_merchant": {"tag": "cobblers_stall"},
      "stalls": [{"id": "c", "town": "t", "sells": "fish", "status": "sited", "category": "Fish",
                  "keeper": {"name": "Fisher"},
                  "stock": [{"item": "minecraft:cod", "count": 4, "price": 80, "gate": None}]},
                 {"id": "d", "town": "northlight", "sells": "fish", "status": "sited", "category": "Fish",
                  "keeper": {"name": "Fisher"},
                  "stock": [{"item": "minecraft:cod", "count": 4, "price": 80, "gate": None}]}]}


def _staff(npcs, lines, plazas=None):
    plazas = plazas or {"towns": {"t": {"stalls": [dict(STALL), dict(STALL, id="t_stall_2", keeper_at=[9, 1, 9, 0])]}}}
    files = {"data/cobblers/function/stalls/merchants/all.mcfunction": ["function cobblers:stalls/merchants/t"],
             "data/cobblers/function/stalls/merchants/t.mcfunction":
                 ["schedule function cobblers:stalls/merchants/t_place 40t replace"],
             "data/cobblers/function/stalls/merchants/t_place.mcfunction": lines}
    summons, kills, fp = A.r17m_merchants(files, ["cobblers:stalls/merchants/all"])
    assert fp == []
    return sorted(p[1] for p in A.staff_checks(plazas, MK, npcs, summons, kills)), summons


def test_staffing_counts_clerks_and_merchants_and_names_each_fault():
    # Without it a stall could stand empty, two keepers share one spot, a keeper stand off every stall, a dialogue
    # stall keeper survive the merchants, or a merchant's removal of the old keeper miss it or take a counter clerk.
    good = [_summon("c", 9, 1, 9), _kill(9, 1, 9), _summon("d", 2, 2, 2), _kill(2, 2, 2)]
    clerk = [("cobblers:npc_market_a", (5, 1, 6), 0)]
    assert _staff(clerk, good)[0] == []
    # two clerks on one seat, the second merchant nowhere
    keys, _s = _staff(clerk + [("cobblers:npc_market_b", (5, 1, 6), 0)], good[2:])
    assert keys == ["c:merchants", "t_stall_1", "t_stall_2"]
    # a Cobblemon dialogue stall keeper still placed by R17M, beside the merchant on its seat
    keys, _s = _staff(clerk + [("cobblers:npc_stall_c", (9, 1, 9), 0)], good)
    assert keys == ["cobblers:npc_stall_c:dialogue", "t_stall_2"]
    # a merchant off every seat in a town that is not a declared fallback; and one with no removal of the old keeper
    keys, _s = _staff(clerk, [_summon("c", 1, 1, 1), _summon("d", 2, 2, 2), _kill(2, 2, 2)])
    assert keys == ["c:replaces", "merchant c:seat", "t_stall_2"]
    # a removal wide enough to reach the clerk at (5, 1, 6) from (9, 1, 9): 5.0 blocks centre to centre
    keys, _s = _staff(clerk, [_summon("c", 9, 1, 9), _kill(9, 1, 9, 5), _summon("d", 2, 2, 2), _kill(2, 2, 2)])
    assert keys == ["c:kills:cobblers:npc_market_a"]
    # turned the wrong way on its seat
    keys, _s = _staff(clerk, [_summon("c", 9, 1, 9, yaw=90.0), _kill(9, 1, 9), _summon("d", 2, 2, 2), _kill(2, 2, 2)])
    assert keys == ["t_stall_2:yaw"]


def test_snbt_reader_by_hand():
    # Without it the merchant's shop could be misread and every shop check would compare the wrong numbers.
    v = A.snbt('{a:1b, "b k":[1.5f,-2],c:"x\\"y",d:{e:[]},f:[I;1,2],g:bare,h:\'q\'}')
    assert v == {"a": 1, "b k": [1.5, -2], "c": 'x"y', "d": {"e": []}, "f": [1, 2], "g": "bare", "h": "q"}
    for bad in ('{a:1', '{a 1}', '[1,2', '{a:1}}'):
        with pytest.raises(ValueError):
            A.snbt(bad)


def test_merchant_shop_must_equal_its_stalls_lines():
    # Without it a merchant could sell at the wrong price, the wrong item, a bulk count, a gated line to everyone, or
    # under no category, and nothing would compare its shop with data/markets.json.
    def run(line, mk=MK):
        summons, _k, _p = A.r17m_merchants({"data/x/function/f.mcfunction": [line]}, ["x:f"])
        return sorted(p[1] for p in A.merchant_checks(mk, summons))
    assert run(_summon("c", 9, 1, 9)) == []
    # $80 for 4 cod is 20 each: 40 each is wrong
    assert run(_summon("c", 9, 1, 9, shop='[{Category:"Fish",Offers:[{Item:{count:1,id:"minecraft:cod"},Price:"40"}]}]')) \
        == ["c:minecraft:cod:price"]
    assert run(_summon("c", 9, 1, 9, shop='[{Category:"Fish",Offers:[{Item:{count:4,id:"minecraft:cod"},Price:"20"}]}]')) \
        == ["c:minecraft:cod:count"]
    assert run(_summon("c", 9, 1, 9, shop='[{Category:"Fish",Offers:[{Item:{count:1,id:"minecraft:salmon"},Price:"20"}]}]')) \
        == ["c:minecraft:cod:missing", "c:minecraft:salmon:extra"]
    assert run(_summon("c", 9, 1, 9, shop='[{Category:"Fowl",Offers:[{Item:{count:1,id:"minecraft:cod"},Price:"20"}]}]')) \
        == ["c:category"]
    assert run(_summon("c", 9, 1, 9, shop='[]')) == ["c:categories"]
    assert run(_summon("c", 9, 1, 9, kind="minecraft:villager", name="Bob")) == ["c:kind", "c:name"]
    assert run(_summon("c", 9, 1, 9).replace("NoAI:1b", "NoAI:0b")) == ["c:NoAI"]
    gated = json.loads(json.dumps(MK))
    gated["stalls"][0]["stock"][0]["gate"] = "badge_1"
    assert run(_summon("c", 9, 1, 9), gated) == ["c:minecraft:cod:gated"]
    gated["stalls"][0]["category"] = ""
    assert "c:category" in run(_summon("c", 9, 1, 9), gated)


def test_r17m_merchants_follows_calls_and_names_a_missing_function():
    # Without it a merchant summoned from a scheduled function would be invisible, or a function R17M names but the
    # pack lacks would read as "no merchants" rather than a fault.
    files = {"data/a/function/x.mcfunction": ["execute if score s o matches 1 run function a:y", "function a:x"],
             "data/a/function/y.mcfunction": ["schedule function a:z 10t append", _summon("c", 1, 2, 3)],
             "data/a/function/z.mcfunction": [_kill(1, 2, 3), "function a:gone"]}
    summons, kills, P = A.r17m_merchants(files, ["a:x"])
    assert [m["block"] for m in summons] == [(1, 2, 3)] and summons[0]["nbt"]["Rotation"] == [0.0, 0.0]
    assert kills == [("data/a/function/z.mcfunction", (1.5, 2.0, 3.5), 2.5)]
    assert [p[1] for p in P] == ["fn:a:gone"]


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
    # 2026-10-05: a hamlet with no Mart, or a place with neither, is exempt ONLY for the door its KNOWN reach entry
    # names (recorded by the squares' builder); a town missing a door with no KNOWN entry still fails here
    for t, r in real["towns"].items():
        missing = {k.split(":", 1)[1] for c, k in A.KNOWN if c == "reach" and k.startswith(t + ":")}
        assert set(r["reach"]) == {"pokecenter", "pokemart"} - missing, t
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


def _markets_files():
    """The markets pack as tools/markets.py emits it now (with whatever mutation is patched in): {path: lines}."""
    import markets
    built, _n = markets.build(markets.load())
    return {k: v for k, v in built.items() if isinstance(v, list)}


def _r17m_fns():
    import markets
    return ["cobblers:markets/load", markets.MERCHANTS_FN]


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
    res = A.audit(None, None, None, npcs=_npcs(), r17m_fns=_r17m_fns(), markets_files=_markets_files())
    caught = {k for c, k, _m in res["problems"] if c == "stall" and k.endswith(":counter")}
    n = sum(len(t["stalls"]) for t in A.load(ROOT / "data" / "plaza_centres.json")["towns"].values())
    assert len(caught) == n == 51     # 43 until 2026-10-05; the six new squares added 8


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
    res = A.audit(None, None, None, npcs=_npcs(), r17m_fns=_r17m_fns(), markets_files=_markets_files())
    dark = {k for c, k, _m in res["problems"] if c == "light"}
    assert len(dark) >= 3, dark


def _staffing(markets_files):
    plazas, mk = A.load(ROOT / "data" / "plaza_centres.json"), A.load(ROOT / "data" / "markets.json")
    summons, kills, fp = A.r17m_merchants(markets_files, _r17m_fns())
    return fp + A.staff_checks(plazas, mk, _npcs(), summons, kills) + A.merchant_checks(mk, summons)


def test_the_committed_markets_staff_every_stall_once_and_every_shop_matches():
    # Without it the mutations below could be "caught" by an audit that fails on the unmutated generator too.
    # Needs no build/: the markets pack is emitted in memory, the expectations are data/.
    assert _staffing(_markets_files()) == []


def test_mutation_merchant_seated_at_the_table_facing_it_is_caught(monkeypatch):
    # Without it a merchant standing in the tent's table, turned from its customers (the old booth's convention), would
    # be reported as staffed: tools/markets.py's own merchant_problems reads the seat through position(), so it passes.
    import markets
    orig = markets.position

    def at_the_table(rec, plazas):
        at, yaw, src = orig(rec, plazas)
        if src != "contract":
            return at, yaw, src
        st = plazas[rec["stall"]]
        return [int(v) for v in st["at"]], (yaw + 180 if yaw <= 0 else yaw - 180), src     # turned to face the table
    monkeypatch.setattr(markets, "position", at_the_table)
    files = _markets_files()
    doc = markets.load()
    assert markets.merchant_problems(doc, files, markets.load_plazas()) == []      # the builder's check passes it
    P = _staffing(files)
    unstaffed = {k for _c, k, _m in P if k.count("_stall_") == 1 and ":" not in k}
    assert len(unstaffed) == 51     # 43 until 2026-10-05; the six new squares added 8


def test_mutation_merchant_price_doubled_is_caught(monkeypatch):
    # Without it a merchant could charge twice its stall's price and the squares' audit would not read its shop.
    # (tools/markets.py's own merchant_problems catches this one too; this proves MY reader reads the summon's text.)
    import markets
    orig = markets.merchant_shop

    def doubled(stall):
        shop = orig(stall)
        for cat in shop:
            for o in cat["Offers"]:
                o["Price"] = str(2 * int(o["Price"]))
        return shop
    monkeypatch.setattr(markets, "merchant_shop", doubled)
    P = _staffing(_markets_files())
    mk = A.load(ROOT / "data" / "markets.json")
    lines = sum(len(s["stock"]) for s in mk["stalls"] if s.get("status") == "sited")
    assert {k for c, k, _m in P} == {k for c, k, _m in P if c == "shop" and k.endswith(":price")}
    assert len(P) == lines > 0


@need_build
def test_mutation_tent_built_without_clearing_its_footprint_is_caught(tmp_path, monkeypatch):
    # Without it a tent built over the old booth would leave the booth's counter log in the keeper's cell (the reason
    # eb71af2 clears the footprint) and the audit would not see it: the builder checks its piece, not the function.
    import re
    import plaza_centre as P
    orig = P.plan_town

    def no_clear(*a, **k):
        cmds, report = orig(*a, **k)
        return [c for c in cmds if not re.fullmatch(r"fill(?: -?\d+){6} minecraft:air", c)], report
    monkeypatch.setattr(P, "plan_town", no_clear)
    _build_into(tmp_path, monkeypatch)
    res = A.audit(None, None, None, npcs=_npcs(), r17m_fns=_r17m_fns(), markets_files=_markets_files())
    caught = {k.rsplit(":", 1)[0] for c, k, _m in res["problems"] if c == "stall" and k.endswith(":air0")}
    n = sum(len(t["stalls"]) for t in A.load(ROOT / "data" / "plaza_centres.json")["towns"].values())
    assert len(caught) == n == 51     # 43 until 2026-10-05; the six new squares added 8
