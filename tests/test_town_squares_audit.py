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
def _market(stock_counter, stock_stall, badge=1, fights=0, produce=0, hours=0):
    """Income 1000 x badge. R2's other terms default to 0, so a ratio is the convenience ask over income."""
    return {"income_basis": {"cumulative_by_badge": {str(b): 1000 * b for b in range(1, 9)}, "target_ratio": 0.7},
            "curve_rule": {"fight_allowance": {"per_leg": fights},
                           "produce_allowance": {"by_badges_held": {str(b): produce for b in range(8)}},
                           "gathering_hours_per_leg": hours},
            "counters": [{"id": "c", "town": "gym1_town", "badge": badge, "status": "sited", "stock": stock_counter}],
            "stalls": [{"id": "s", "town": "gym1_town", "badge": badge, "status": "sited", "sells": "fish",
                        "stock": stock_stall}]}


TOWNS = {"towns": [{"id": "gym1_town", "critical_path": True}, {"id": "sea_town", "critical_path": False}]}
# a gathering tier worth 2/h x $10 = $20 an hour from leg 1, and a second worth that + 1/h x $30 = $50 from leg 3
EFFORT = {"effort_model": {"tiers": {"early": {"from_tiers": ["early"], "opens_leg": 1},
                                     "deep": {"from_tiers": ["early", "deep"], "opens_leg": 3}}},
          "buys": [{"item": "x:ore", "tier": "early", "rate_per_hour": 2, "price": 10},
                   {"item": "x:gem", "tier": "deep", "rate_per_hour": 1, "price": 30}]}


def _l(i, price, strand="convenience", **kw):
    return dict({"id": i, "item": "x:" + i, "price": price, "gate": None, "strand": strand}, **kw)


def test_curve_counts_only_convenience_lines_of_counters_and_stalls():
    # ECONOMY_OVERHAUL R2: "power lines leave it". Without it a power line would weigh on the money curve again, a
    # stall's convenience line could move it unseen, or a pick-one group be counted in full.
    counter = [_l("a", 300), _l("b", 200, group="g"), _l("c", 500, group="g"),
               _l("d", 9000, stretch=True), _l("tm", 7000, "power")]
    stall = [dict(_l("e", 100, "provision"), item="minecraft:cod"), dict(_l("f", 40), item="minecraft:salmon")]
    rows = A.curve(_market(counter, stall), TOWNS, EFFORT)
    assert rows[0] == (1, 300 + 500 + 40, 1000, 0.84)          # a, g at its dearest, f; not d, tm or e
    assert rows[7][1] == 840                                   # nothing after badge 1


def test_earned_by_badge_adds_produce_and_one_gathering_hour_a_leg_by_hand():
    # R2's denominator. By hand with fights 100, produce 50 a leg, 1 hour a leg: leg 1-2 at the early tier's $20,
    # legs 3-8 at the deep tier's $50. Badge 3: income 3000 + produce 150 + gathering 20 + 20 + 50 = 3240, fights 300.
    # Without it the produce allowance or the gathering hour could silently drop out of the curve.
    e = A.earned_by_badge(_market([], [], fights=100, produce=50, hours=1), EFFORT)
    assert e[1] == (100, 1000 + 50 + 20) and e[2] == (200, 2000 + 100 + 40) and e[3] == (300, 3240)
    assert e[8] == (800, 8000 + 400 + 40 + 6 * 50)
    rows = A.curve(_market([_l("a", 1000)], [], fights=100, produce=50, hours=1), TOWNS, EFFORT)
    assert rows[0] == (1, 1100, 1070, round(1100 / 1070, 4))


def test_mutation_the_gathering_rate_input_moves_the_curve():
    # Mutates the INPUT (data/bank.json's effort rates), never the record under test: the early hour doubles to $40
    # and badge 1's earned rises by 20. Without it the gathering term could be a constant.
    rich = json.loads(json.dumps(EFFORT))
    rich["buys"][0]["rate_per_hour"] = 4
    mk = _market([_l("a", 1000)], [], hours=1)
    assert A.curve(mk, TOWNS, rich)[0][2] - A.curve(mk, TOWNS, EFFORT)[0][2] == 20


def test_curve_check_names_an_unknown_strand_and_a_missing_basis():
    # Fail closed: a critical-path line of no strand cannot be placed on either side of R2's split, and a curve whose
    # curve_rule is gone cannot be computed. Without it both would pass as an empty ask.
    P, _r = A.curve_checks(_market([{"id": "a", "item": "x:a", "price": 100, "gate": None}], []), TOWNS, EFFORT)
    assert [k for _c, k, _m in P] == ["strand:c:a"]
    mk = _market([_l("a", 100)], [])
    del mk["curve_rule"]
    P, rows = A.curve_checks(mk, TOWNS, EFFORT)
    assert [k for _c, k, _m in P] == ["basis"] and rows == []


def test_power_rule_flags_an_ungated_ball_and_passes_a_badge_gated_one():
    # Without it a stall could sell Ultra Balls from the first visit.
    doc = _market([{"id": "u", "item": "cobblemon:ultra_ball", "price": 1, "gate": "gym6_cleared"}],
                  [{"id": "b", "item": "cobblemon:great_ball", "price": 1, "gate": None},
                   {"id": "k", "item": "minecraft:dried_kelp", "price": 1, "gate": None},
                   {"id": "p", "item": "minecraft:splash_potion", "price": 1, "gate": None}])
    P, _u = A.item_checks(doc, set(), {})
    assert sorted(p[1] for p in P if p[0] == "power") == ["s:cobblemon:great_ball", "s:minecraft:splash_potion"]


def test_power_rule_accepts_a_gate_dropped_by_a_recorded_decision_only():
    # 2026-10-06 (the owner: "should be the villagers with ui only"): a counter is a merchant and cannot gate, so a
    # ball whose badge gate was dropped BY A DECISION data/markets.json records passes; the same record citing a
    # decision nobody took, or naming no badge, still fails. Without it the rule would either fail every counter or
    # wave through any ungated ball.
    drop = lambda **kw: dict({"gate": "gym6_cleared", "decision": "counters_are_merchants", "why": "probe"}, **kw)
    doc = _market([{"id": "u", "item": "cobblemon:ultra_ball", "price": 1, "gate": None, "gate_dropped": drop()},
                   {"id": "v", "item": "cobblemon:great_ball", "price": 1, "gate": None,
                    "gate_dropped": drop(decision="nobody_decided")},
                   {"id": "w", "item": "cobblemon:net_ball", "price": 1, "gate": None, "gate_dropped": drop(gate=None)}],
                  [])
    doc["decisions"] = [{"id": "counters_are_merchants"}]
    P, _u = A.item_checks(doc, set(), {})
    assert sorted(p[1] for p in P if p[0] == "power") == ["c:cobblemon:great_ball", "c:cobblemon:net_ball"]


def _price_gated(price, badge, count=1, **kw):
    return dict({"id": "t%d_%d" % (price, badge), "item": "tmcraft:tm_probe_%d_%d" % (price, badge), "count": count,
                 "price": price, "gate": None, "gate_badge": badge}, **kw)


def test_power_rule_counter_price_above_its_income_gate_passes_and_below_or_undeclared_fails():
    # 2026-10-09 (the owner: "price them above the income gate. A TM costing less than a player earns before badge 1
    # is free"): on a counter the price is the gate. Income here is 1000 x badge, so by hand: badge 2's gate is 2000.
    # Without it a TM priced under what the road pays would pass as gated, or every counter TM would fail forever.
    doc = _market([_price_gated(2001, 2),                       # one dollar above: passes
                   _price_gated(2000, 2),                       # equal is not above: fails
                   _price_gated(1999, 2),                       # below: fails
                   _price_gated(4002, 2, count=2),              # 2001 a unit: passes
                   _price_gated(4000, 2, count=2),              # 2000 a unit, the line's 4000 is no excuse: fails
                   _price_gated(9001, 9),                       # no badge 9 in the income basis: fails
                   dict(_price_gated(5000, 1), gate_badge=True),  # a bool is not a badge: fails
                   {"id": "nd", "item": "tmcraft:tm_nodecl", "price": 9000, "gate": None}],  # declares nothing
                  [dict(_price_gated(2001, 2), item="cobblemon:ultra_ball")])   # a stall: price gates nothing
    P, _u = A.item_checks(doc, set(), {})
    power = {p[1]: p[2] for p in P if p[0] == "power"}
    assert sorted(power) == sorted(["c:tmcraft:tm_probe_2000_2", "c:tmcraft:tm_probe_1999_2",
                                    "c:tmcraft:tm_probe_4000_2", "c:tmcraft:tm_probe_9001_9",
                                    "c:tmcraft:tm_probe_5000_1", "c:tmcraft:tm_nodecl",
                                    "s:cobblemon:ultra_ball"])
    assert "not above the 2000 earned by badge 2" in power["c:tmcraft:tm_probe_2000_2"]
    assert "declares no gate_badge" in power["c:tmcraft:tm_nodecl"]
    assert "no figure for" in power["c:tmcraft:tm_probe_9001_9"]


FIXTURE_2833317 = ROOT / "tests" / "fixtures" / "counter_lines_2833317.json"


def _with_2833317(price_of=None, badge_of=None):
    """The committed data/markets.json, in memory, with the 41 counter lines 2833317 added (held out by e41b72e)
    put back on their counters. price_of/badge_of(counter, line) -> the line's price / declared gate_badge (None:
    declare none). The file on disk is not touched."""
    import copy
    mk = copy.deepcopy(A.load(ROOT / "data" / "markets.json"))
    fx = A.load(FIXTURE_2833317)["counters"]
    by = {c["id"]: c for c in mk["counters"]}
    for cid, lines in fx.items():
        for l in copy.deepcopy(lines):
            if badge_of is not None and badge_of(by[cid], l) is not None:
                l["gate_badge"] = badge_of(by[cid], l)
            if price_of is not None:
                l["price"] = price_of(by[cid], l)
            by[cid]["stock"].append(l)
    return mk, {(cid, l["item"]) for cid, ls in fx.items() for l in ls}


def _tm_badge(counter, line):
    """The badge each 2833317 line was priced at, from its own words ('5% of income at badge N'); else the
    counter's badge (the memories and the Sachet)."""
    import re
    m = re.search(r"at badge (\d)", line.get("why") or "")
    return int(m.group(1)) if m else counter["badge"]


def _power_keys(mk):
    P, _u = A.item_checks(mk, set(), {})
    return {p[1]: p[2] for p in P if p[0] == "power"}


def test_the_2833317_counter_lines_fail_at_their_old_prices_with_or_without_a_declared_gate():
    # The 41 lines 2833317 put on Fossick and Northlight (23 TMs at 5% of income, 17 memories, the Sachet). Without
    # it they could go back on sale at $500-$7,300 against what the road pays by their badge (income_basis), which the
    # owner calls free.
    inc = A.load(ROOT / "data" / "markets.json")["income_basis"]["cumulative_by_badge"]
    base = set(_power_keys(A.load(ROOT / "data" / "markets.json")))
    mk, added = _with_2833317()
    assert len(added) == 41 and sum(1 for _c, i in added if i.startswith("tmcraft:tm_")) == 23
    want = {"%s:%s" % k for k in added}
    got = _power_keys(mk)
    assert set(got) - base == want                                      # every one, nothing else
    assert all("declares no gate_badge" in got[k] for k in want)
    mk, _a = _with_2833317(badge_of=_tm_badge)                          # declared, still at the old prices
    got = _power_keys(mk)
    assert set(got) - base == want
    assert all("not above the" in got[k] for k in want)
    assert "one costs 500, not above the %d earned by badge 1" % inc["1"] in got["fossick:tmcraft:tm_bide"]


def test_the_2833317_counter_lines_pass_one_dollar_above_their_declared_income_gate():
    # The same 41 lines re-priced by hand to the income basis + $1 a unit, each declaring its badge: none fails, and
    # the audit's power findings are back to the committed data's (the KNOWN set is not disturbed). Without it the
    # rule could fail a correctly re-priced line and the builder would have no price that passes.
    inc = A.load(ROOT / "data" / "markets.json")["income_basis"]["cumulative_by_badge"]
    base = _power_keys(A.load(ROOT / "data" / "markets.json"))
    mk, _a = _with_2833317(badge_of=_tm_badge,
                           price_of=lambda c, l: (inc[str(_tm_badge(c, l))] + 1) * (l.get("count") or 1))
    assert _power_keys(mk) == base


def test_mutation_the_income_basis_raised_one_dollar_fails_every_line_priced_one_above_it():
    # Mutates the INPUT the threshold comes from (income_basis.cumulative_by_badge), with every line record left as
    # the previous test priced it: all 41 must flip to failing. Without it the gate could be a constant, or read from
    # the line itself (a record-side check moves with the record and proves nothing).
    import copy
    inc = A.load(ROOT / "data" / "markets.json")["income_basis"]["cumulative_by_badge"]
    base = set(_power_keys(A.load(ROOT / "data" / "markets.json")))
    mk, added = _with_2833317(badge_of=_tm_badge,
                              price_of=lambda c, l: (inc[str(_tm_badge(c, l))] + 1) * (l.get("count") or 1))
    assert set(_power_keys(mk)) == base
    raised = copy.deepcopy(mk)
    raised["income_basis"]["cumulative_by_badge"] = {k: v + 1 for k, v in inc.items()}
    assert set(_power_keys(raised)) - base == {"%s:%s" % k for k in added}
    gone = copy.deepcopy(mk)
    del gone["income_basis"]["cumulative_by_badge"]                     # the basis missing: nothing can pass by price
    assert set(_power_keys(gone)) - base == {"%s:%s" % k for k in added}


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


# counter a is sited, a merchant since 2026-10-06 (data/markets.json decisions counters_are_merchants); b is not
MK = {"counters": [{"id": "a", "town": "t", "status": "sited", "category": "Fish", "keeper": {"name": "Fisher"},
                    "stock": [{"item": "minecraft:cod", "count": 4, "price": 80, "gate": None}]},
                   {"id": "b", "town": "t"}],
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


def test_staffing_counts_merchants_and_names_each_fault():
    # Without it a stall could stand empty, two keepers share one spot, a keeper stand off every stall, a dialogue
    # keeper (a stall's, or since 2026-10-06 a counter's) survive the merchants, or a merchant's removal of the old
    # keeper miss it or take another NPC R17M places. Counter a's keeper is a merchant on t_stall_1's seat.
    a = [_summon("a", 5, 1, 6), _kill(5, 1, 6)]
    good = a + [_summon("c", 9, 1, 9), _kill(9, 1, 9), _summon("d", 2, 2, 2), _kill(2, 2, 2)]
    assert _staff([], good)[0] == []
    # the counter's merchant missing, and the first stall's: both seats empty
    keys, _s = _staff([], good[4:])
    assert keys == ["a:merchants", "c:merchants", "t_stall_1", "t_stall_2"]
    # a Cobblemon dialogue keeper still placed by R17M beside the merchant on its seat: the counter's, then a stall's
    keys, _s = _staff([("cobblers:npc_market_a", (5, 1, 6), 0)], good)
    assert keys == ["cobblers:npc_market_a:dialogue", "t_stall_1"]
    keys, _s = _staff([("cobblers:npc_stall_c", (9, 1, 9), 0)], good)
    assert keys == ["cobblers:npc_stall_c:dialogue", "t_stall_2"]
    # a merchant off every seat in a town that is not a declared fallback; and one with no removal of the old keeper
    keys, _s = _staff([], a + [_summon("c", 1, 1, 1), _summon("d", 2, 2, 2), _kill(2, 2, 2)])
    assert keys == ["c:replaces", "merchant c:seat", "t_stall_2"]
    # the counter's merchant with no removal: its Steve stays (the owner, 2026-10-06: "need the steve traders gone")
    keys, _s = _staff([], [_summon("a", 5, 1, 6)] + good[2:])
    assert keys == ["a:replaces"]
    # a removal wide enough to reach another NPC R17M places, at (12, 1, 9) from (9, 1, 9): 3.0 blocks centre to
    # centre (a dialogue keeper is the removal's target, never its victim, so the victim here is another class)
    keys, _s = _staff([("cobblers:npc_other", (12, 1, 9), 0)],
                      a + [_summon("c", 9, 1, 9), _kill(9, 1, 9, 5), _summon("d", 2, 2, 2), _kill(2, 2, 2)])
    assert keys == ["c:kills:cobblers:npc_other", "cobblers:npc_other"]
    # turned the wrong way on its seat
    keys, _s = _staff([], a + [_summon("c", 9, 1, 9, yaw=90.0), _kill(9, 1, 9), _summon("d", 2, 2, 2), _kill(2, 2, 2)])
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
    # a counter's merchant is held to its own lines the same way (2026-10-06), and may not be gated either
    assert run(_summon("a", 5, 1, 6)) == []
    assert run(_summon("a", 5, 1, 6, shop='[{Category:"Fish",Offers:[{Item:{count:1,id:"minecraft:cod"},Price:"40"}]}]')) \
        == ["a:minecraft:cod:price"]
    gated = json.loads(json.dumps(MK))
    gated["counters"][0]["stock"][0]["gate"] = "badge_1"
    assert run(_summon("a", 5, 1, 6), gated) == ["a:minecraft:cod:gated"]


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


def test_curve_is_unchanged_by_the_stalls():
    # Without it a stall's convenience line could quietly move the critical path's ask.
    mk = A.load(ROOT / "data" / "markets.json")
    towns = A.load(ROOT / "data" / "towns.json")
    rows = A.curve(mk, towns)
    assert A.curve(dict(mk, stalls=[]), towns) == rows
    P, _rows = A.curve_checks(mk, towns)
    assert [k for _c, k, _m in P if not k.startswith("badge")] == [], P


# Strict: under R2 the committed convenience strand reads 1.37 at badge 1 down to 0.38 at badge 8 (the slope
# ECONOMY_OVERHAUL 1.2 predicted), so badges 1-4 are over the 0.70 target. It XPASSes -- failing the run -- the day
# the strand is re-priced, and the xfail must then go.
@pytest.mark.xfail(strict=True, reason="data/markets.json's convenience lines are not yet re-priced to R2's curve "
                                       "(ECONOMY_OVERHAUL build list U5: markets.py prices --write)")
def test_the_committed_curve_is_inside_the_target():
    mk = A.load(ROOT / "data" / "markets.json")
    P, _rows = A.curve_checks(mk, A.load(ROOT / "data" / "towns.json"))
    assert P == [], P


def test_curve_check_names_a_stall_convenience_line_and_lets_a_counter_reprice_through():
    # The check pins "the stalls moved no money", derived from the data, not a constant curve. By hand: a counter at
    # badge 1 asking 600 against 1000 earned (0.60). A 40 convenience line on a stall at badge 1 moves badges 1-8 by
    # 40 and is named; re-pricing the counter 600 -> 650 (a deliberate counter change, markets_audit's to judge) is
    # not; a re-price to 750 (0.75) still fails the 0.70 target. Without it either a stall could move the ladder
    # unseen, or every deliberate counter re-price would fail this audit forever (the 2026-10-09 Holdfast prices did).
    counter = [_l("a", 600)]
    stall = [dict(_l("f", 40), item="minecraft:salmon"),
             dict(_l("e", 100, "provision"), item="minecraft:cod")]                  # provision: never counted
    P, _r = A.curve_checks(_market(counter, stall), TOWNS, EFFORT)
    assert [k for _c, k, _m in P] == ["stalls"]
    assert "[(1, 40), (2, 40), (3, 40), (4, 40), (5, 40), (6, 40), (7, 40), (8, 40)]" in P[0][2]
    P, _r = A.curve_checks(_market([dict(counter[0], price=650)], stall[1:]), TOWNS, EFFORT)
    assert P == []
    P, _r = A.curve_checks(_market([dict(counter[0], price=750)], stall[1:]), TOWNS, EFFORT)
    assert [k for _c, k, _m in P] == ["badge1"]


def test_curve_check_follows_the_real_counters_when_a_counter_line_is_repriced():
    # Mutates the committed data in memory (the file is untouched). Holdfast's Inception Upgrade (convenience) down
    # 500 moves badge 8's ask by -500 and nothing before it; Holdfast's Full Restore (power) moved by 500 moves
    # nothing at all (R2: power lines leave the curve). The check stays silent on the stalls either way. Without it
    # the audit could regain a hard-coded curve, or start counting power lines again.
    import copy
    mk = copy.deepcopy(A.load(ROOT / "data" / "markets.json"))
    towns = A.load(ROOT / "data" / "towns.json")
    before = A.curve(mk, towns)
    hold = next(c for c in mk["counters"] if c["id"] == "holdfast")
    power = next(l for l in hold["stock"] if l["item"] == "cobblemon:full_restore")
    assert power["strand"] == "power"
    power["price"] -= 500
    assert A.curve(mk, towns) == before
    conv = next(l for l in hold["stock"] if l["item"] == "sophisticatedbackpacks:inception_upgrade")
    assert conv["strand"] == "convenience"
    conv["price"] -= 500
    after = A.curve(mk, towns)
    assert [a for _b, a, _i, _r in before][:7] == [a for _b, a, _i, _r in after][:7]
    assert before[7][1] - after[7][1] == 500
    P, _r = A.curve_checks(mk, towns)
    assert [k for _c, k, _m in P if k == "stalls"] == []


def test_a_trade_evolution_item_is_power_like_a_stone_and_passes_only_with_a_recorded_gate_drop():
    # A Link Cable evolves a Kadabra, a Machoke, a Haunter or a Graveler: a power step like an evolution stone (the
    # stones are power here, KNOWN at Steepside). On a counter it passes the way its siblings on the same counters
    # (the Metal Coat, the Dubious Disc) pass: a gate_dropped record citing a decision data/markets.json holds. Without
    # it a new evolution item could go on sale from the first visit with nothing recording why.
    drop = {"gate": "gym3_cleared", "decision": "counters_are_merchants", "why": "probe"}
    doc = _market([{"id": "lc", "item": "cobblemon:link_cable", "price": 2160, "gate": None},
                   {"id": "mc", "item": "cobblemon:metal_coat", "price": 2160, "gate": None, "gate_dropped": drop}], [])
    doc["decisions"] = [{"id": "counters_are_merchants"}]
    P, _u = A.item_checks(doc, set(), {})
    assert [p[1] for p in P if p[0] == "power"] == ["c:cobblemon:link_cable"]


def _jar(path, files):
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        for name, body in files.items():
            z.writestr(name, body if isinstance(body, (str, bytes)) else json.dumps(body))


def test_an_item_exists_by_its_lang_key_or_by_model_and_tag_together_never_by_one_alone(tmp_path):
    # TMCraft's per-move TMs have an item model and an item-tag entry and no lang key. By hand, one synthetic jar:
    #   tm_both   model + tag              -> exists
    #   tm_model  model only               -> fails (a model can exist for an unregistered id)
    #   tm_tag    tag only                 -> fails (a tag is data any pack can write)
    #   tm_opt    model + {"required": false} tag entry -> fails (an optional entry is no evidence)
    #   tm_ref    model + "#tmcraft:tm_ref" (a tag reference, not an item) -> fails
    #   named     lang key only            -> exists (the old rule, unchanged)
    # and the same in a jar nested under META-INF/jars/. Without it the 7 TMCraft TMs on the counters fail as
    # missing, or a model file alone would let a typo'd id through.
    model = {"parent": "item/generated"}
    _jar(tmp_path / "inner.jar", {"assets/nest/models/item/deep.json": model,
                                  "data/nest/tags/item/all.json": {"values": ["nest:deep"]}})
    (tmp_path / "mods").mkdir()
    _jar(tmp_path / "mods" / "tm.jar", {
        "assets/tmcraft/lang/en_us.json": {"item.tmcraft.named": "Named", "itemGroup.tmcraft": "x"},
        "assets/minecraft/lang/en_us.json": {"item.minecraft.stick": "Renamed Stick"},   # a mod's override
        "assets/tmcraft/models/item/tm_both.json": model,
        "assets/tmcraft/models/item/tm_model.json": model,
        "assets/tmcraft/models/item/tm_opt.json": model,
        "assets/tmcraft/models/item/tm_ref.json": model,
        "data/tmcraft/tags/item/tm_moves.json": {"values": ["tmcraft:tm_both", "tmcraft:tm_tag", "#tmcraft:tm_ref",
                                                            {"id": "tmcraft:tm_opt", "required": False}]},
        "META-INF/jars/inner.jar": (tmp_path / "inner.jar").read_bytes(),
    })
    ids, notes = A.jar_index(None, tmp_path / "mods")
    assert ids["tmcraft"] == {"named", "tm_both"}
    assert ids["nest"] == {"deep"}
    assert any("2 id(s) with no lang key accepted" in n for n in notes), notes
    # no vanilla jar: a mod's one-key minecraft lang override is not the vanilla list, so minecraft: is unchecked
    # (named as such), never failed against that fragment
    assert "minecraft" not in ids
    _P, unchecked = A.item_checks(_market([{"id": "w", "item": "minecraft:wheat", "price": 1, "gate": None}], []),
                                  set(), ids)
    assert unchecked == {"minecraft"} and _P == []
    stock = [{"id": p, "item": "tmcraft:%s" % p, "price": 1, "gate": None}
             for p in ("tm_both", "tm_model", "tm_tag", "tm_opt", "tm_ref", "named")]
    P, _u = A.item_checks(_market(stock, []), set(), ids)
    assert sorted(p[1] for p in P if p[0] == "items") == ["c:tmcraft:tm_model:exists", "c:tmcraft:tm_opt:exists",
                                                          "c:tmcraft:tm_ref:exists", "c:tmcraft:tm_tag:exists"]


SNAPSHOT_MODS = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods")


@pytest.mark.skipif(not SNAPSHOT_MODS.is_dir(), reason="needs the 2026-10-05 offline server snapshot's mods/ at %s"
                    % SNAPSHOT_MODS)
def test_every_counter_and_stall_item_is_in_the_snapshot_jars():
    # The committed stock against the real jars (the offline snapshot, never the live server): no item is missing,
    # and an id TMCraft does not ship still is. Without it a TM with no lang key would fail as missing, and an id
    # nobody registers could be sold as a blank slot. Minecraft ids are judged only when the vanilla jar is present.
    ids, _n = A.jar_index(A.DEFAULT_VANILLA if A.DEFAULT_VANILLA.is_file() else None, SNAPSHOT_MODS)
    mk = A.load(ROOT / "data" / "markets.json")
    P, _u = A.item_checks(mk, set(), ids)
    assert [m for c, _k, m in P if c == "items"] == []
    assert "tm_bide" in ids["tmcraft"] and "tm_not_a_move" not in ids["tmcraft"]


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
    assert len(caught) == n == 49     # 43 until 2026-10-05; the six new squares added 8, the Displaced City's 2 held (data/held/)


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
    assert len(unstaffed) == 49     # 43 until 2026-10-05; the six new squares added 8, the Displaced City's 2 held (data/held/)


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
    # every sited stall's line, and since 2026-10-06 every sited counter's (the counters are merchants)
    lines = sum(len(s["stock"]) for s in mk["stalls"] + mk["counters"] if s.get("status") == "sited")
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
    assert len(caught) == n == 49     # 43 until 2026-10-05; the six new squares added 8, the Displaced City's 2 held (data/held/)
