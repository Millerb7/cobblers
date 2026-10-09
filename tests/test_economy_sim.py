"""Tests for tools/economy_sim.py: the simulation reproduces, reads its prices from data, and agrees with the sources it
did not derive from (the dungeon audit's generated boss classes, income_basis's exact expectation, the curve's ratio).

A mutation test here changes the DATA a world is built from, never the sim's code and never the result: if a price moves
and the output does not, the sim is not reading it.
"""
from __future__ import annotations

import copy
import json
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import economy_sim as E  # noqa: E402


@pytest.fixture(scope="module")
def docs():
    return E.load_docs()


@pytest.fixture(scope="module")
def world(docs):
    return E.World(docs)


def world_with(docs, mutate, **kw):
    d = copy.deepcopy(docs)
    mutate(d)
    return E.World(d, **kw)


def run(w, ptypes, scenarios, runs=40, seed=5):
    return E.simulate(w, ptypes=ptypes, scenarios=scenarios, runs=runs, seed=seed)


def stage(sim, sn, pt, key):
    return next(x for x in sim[sn][pt] if x["stage"] == key)


# ---------------------------------------------------------------------------------------------------- reproducibility


def test_a_fixed_seed_reproduces_and_another_differs(world):
    a = run(world, ["steady", "greedy"], ["as_built"], runs=25, seed=3)
    b = run(world, ["steady", "greedy"], ["as_built"], runs=25, seed=3)
    c = run(world, ["steady", "greedy"], ["as_built"], runs=25, seed=4)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert json.dumps(a, sort_keys=True) != json.dumps(c, sort_keys=True)


def test_a_run_is_nonempty_and_has_dungeon_activity(world):
    sim = run(world, ["greedy"], ["as_built"], runs=30)
    g = sim["as_built"]["greedy"]
    assert [x["stage"] for x in g][:2] == ["1", "2"] and g[-1]["stage"] == "champion"
    assert sum(x["dungeon"]["runs"] for x in g) >= 8 * 4
    assert sum(x["ledger"]["seam"] for x in g) > 0


# ---------------------------------------------------------------------------------------------------- the payout


def hand_range(levels, mult=1.25):
    """Written out in the test from the formula, sharing nothing with the sim."""
    s = sum(levels)
    f = 0.0
    for lv in levels:
        f += lv / 50.0
    b = max(1, int(5 * s * f))
    return int((b + b // 2) * mult), int((b + 2 * b) * mult)


def hand_boss_teams(docs):
    d = docs["dungeons"]["dungeons"][0]["boss"]
    out = {}
    for band in docs["dungeons"]["engine"]["bands"]:
        base = min(band["caps"])
        stages = []
        n = len(d["stage_level_offsets"])
        for i, off in enumerate(d["stage_level_offsets"], 1):
            lv = [base + off]
            if i == n and band["band"] >= d["escort_from_band"]:
                lv.append(base + d["escort_level_offset"])
            stages.append(lv)
        out[band["band"]] = stages
    return out


def test_boss_payout_per_run_matches_hand_arithmetic(world, docs):
    for band, stages in hand_boss_teams(docs).items():
        lo = sum(hand_range(t)[0] for t in stages)
        hi = sum(hand_range(t)[1] for t in stages)
        got = [world.credit_range(t) for t in world.boss_teams[band]]
        assert (sum(g[0] for g in got), sum(g[1] for g in got)) == (lo, hi), band


def test_the_published_band_ranges(world):
    # the three figures the brief relays (the engine audit's); re-derived here, not trusted
    def run_range(b):
        r = [world.credit_range(t) for t in world.boss_teams[b]]
        return sum(x[0] for x in r), sum(x[1] for x in r)
    assert run_range(1) == (202, 405)
    assert run_range(3) == (855, 1710)
    assert run_range(6) == (11062, 22125)


def test_sim_boss_teams_equal_the_generated_npc_classes(world):
    import dungeon_audit as DA
    got = DA.boss_payouts(DA.dungeon_files())
    for band, (lo, hi) in got.items():
        r = [world.credit_range(t) for t in world.boss_teams[band]]
        assert (sum(x[0] for x in r), sum(x[1] for x in r)) == (lo, hi), band


def test_drawn_credit_is_inside_its_range_and_has_the_right_mean(world):
    rng = random.Random(9)
    team = [58, 59]
    lo, hi = world.credit_range(team)
    xs = [world.credit(team, rng) for _ in range(20000)]
    assert min(xs) >= lo and max(xs) <= hi
    s = sum(team)
    b = s * s // 10
    expect = 1.25 * (b + (b // 2 + 2 * b) / 2.0)
    assert abs(sum(xs) / len(xs) - expect) / expect < 0.01


def test_simulated_fights_match_income_basis_exact_expectation(world, docs):
    sim = run(world, ["fighter"], ["design"], runs=400, seed=11)
    got = sum(stage(sim, "design", "fighter", str(n))["ledger"]["fights"] for n in range(1, 9))
    want = docs["markets"]["income_basis"]["exact_expectation"]["normal_cumulative_by_badge"]["8"]
    assert abs(got - want) / want < 0.02


def test_challenge_mode_uses_the_challenge_rosters(world):
    sim = run(world, ["fighter", "challenge"], ["design"], runs=60)
    f = stage(sim, "design", "fighter", "8")["ledger"]["fights"]
    c = stage(sim, "design", "challenge", "8")["ledger"]["fights"]
    assert c > f * 1.2


# ---------------------------------------------------------------------------------------------------- the model's own anchors


def test_the_curve_ratio_is_reproduced_with_no_dungeons(world):
    """The baseline player (the model before dungeons) spends the curve's 0.65-0.70 of what trainers, gathering and the
    produce buyer pay: the sim agrees with tools/markets.py curve, which it does not call."""
    sim = run(world, ["baseline"], ["design"], runs=150, seed=2)
    for k in ("3", "5", "7"):
        led = stage(sim, "design", "baseline", k)["ledger"]
        spend = -(led["essentials"] + led["deaths"] + led["shelf"])
        inc = led["fights"] + led["gather"] + led["produce"]
        assert 0.62 <= spend / inc <= 0.72, (k, spend / inc)


def test_required_minutes_and_clocks_agree(world):
    for band, req in E.REQUIRED_MIN.items():
        assert math.ceil(req * 1.25) == round(world.clock_min[band]), band


def test_sigil_values_are_the_bank_values_in_the_design(world):
    assert [world.sigil_value[b] for b in range(1, 7)] == [39, 62, 160, 262, 900, 1708]


def test_bands_follow_the_level_cap(world):
    got = [world.band_of(k) for k in range(9)]
    assert got == [1, 1, 2, 2, 3, 3, 4, 4, 5]
    assert world.band_of(8, champion=True) == 6


def test_the_ladder_rates(world):
    assert [world.mult_of(t) for t in (0, 4, 5, 9, 10, 15, 20, 24)] == [1, 1, 1.25, 1.25, 1.5, 2, 3, 3]


def test_the_sim_refuses_a_world_where_wild_battles_pay(docs):
    d = copy.deepcopy(docs)
    d["cd"]["earnCobbleDollarsFromWildPokemon"] = True
    with pytest.raises(E.SimError):
        E.World(d)


# ---------------------------------------------------------------------------------------------------- the defects


def test_the_clawback_scenario_pays_no_boss_money_and_the_defect_does(world):
    sim = run(world, ["greedy"], ["design", "as_built"], runs=40)
    d = sum(x["ledger"]["boss_pay"] for x in sim["design"]["greedy"])
    a = sum(x["ledger"]["boss_pay"] for x in sim["as_built"]["greedy"])
    assert d == 0 and a > 10000


def test_defect_one_alone_accounts_for_the_boss_money(world):
    sim = run(world, ["steady"], ["design", "defect1", "defect2", "as_built"], runs=60, seed=8)
    end = lambda sn: stage(sim, sn, "steady", "hq_tower")["savings"]  # noqa: E731
    assert end("defect1") > end("design")
    # the recipe window can only overpay, by at most one sigil's difference
    assert end("defect2") <= end("design")
    assert end("design") - end("defect2") <= max(world.sigil_value[b + 1] - world.sigil_value[b] for b in range(1, 6))
    # and the two together are the sum of the parts (paired draws)
    assert abs((end("as_built") - end("design")) - ((end("defect1") - end("design")) + (end("defect2") - end("design")))) < 1e-6


def test_unclawed_stands_would_print_money(world):
    rows = E.dungeon_table(world, runs=400, seed=1, p_stage=0.9, scenarios=("as_built", "stands_unclawed"))
    par = E.parity_hours(world)
    for band in (2, 4, 6):
        s = E.best_row(rows, band, "stands_unclawed")
        assert s["net_h"] > par[band][0], band      # past parity: the clawback must exist before the stands do


def test_as_built_dungeon_hour_stays_under_parity_in_every_band(world):
    rows = E.dungeon_table(world, runs=800, seed=1, p_stage=0.97, scenarios=("as_built",))
    par = E.parity_hours(world)
    for band in par:
        assert E.best_row(rows, band, "as_built")["net_h"] < par[band][0], band


# ---------------------------------------------------------------------------------------------------- mutations of DATA


def test_a_bank_price_moves_the_sigil_the_seam_and_the_result(docs):
    def dia(d):
        for b in d["bank"]["buys"]:
            if b["item"] == "minecraft:diamond":
                b["price"] = 360
    w0, w1 = E.World(docs), world_with(docs, dia)
    assert w1.sigil_value[3] == w0.sigil_value[3] + 240
    assert w1.expected_face_value(6) > w0.expected_face_value(6)
    r0 = E.best_row(E.dungeon_table(w0, runs=400, seed=2, scenarios=("design",)), 3, "design")
    r1 = E.best_row(E.dungeon_table(w1, runs=400, seed=2, scenarios=("design",)), 3, "design")
    assert r1["net"] < r0["net"]


def test_a_blackout_charge_moves_the_dungeon_death_cost(docs):
    w0 = E.World(docs)
    w1 = world_with(docs, lambda d: d["blackout"]["money"].update(cap=6000))
    assert w1.blackout == 2 * w0.blackout
    a = run(w0, ["steady"], ["design"], runs=60, seed=4)
    b = run(w1, ["steady"], ["design"], runs=60, seed=4)
    assert stage(b, "design", "steady", "4")["ledger"]["dungeon_deaths"] < stage(a, "design", "steady", "4")["ledger"]["dungeon_deaths"]
    assert stage(b, "design", "steady", "8")["savings"] < stage(a, "design", "steady", "8")["savings"]


def test_a_shelf_price_moves_the_savings(docs):
    def dear(d):
        for c in d["markets"]["counters"]:
            if c["path"] == "critical":
                for it in c["stock"]:
                    if it.get("strand") == "convenience" and not it.get("stretch"):
                        it["price"] = it["price"] * 4
    w0, w1 = E.World(docs), world_with(docs, dear)
    assert sum(sum(v) for v in w1.shelf_due.values()) > 3 * sum(sum(v) for v in w0.shelf_due.values())
    a = run(w0, ["steady"], ["design"], runs=40)
    b = run(w1, ["steady"], ["design"], runs=40)
    assert stage(b, "design", "steady", "8")["savings"] < stage(a, "design", "steady", "8")["savings"]
    assert stage(b, "design", "steady", "2")["backlog_p"] > stage(a, "design", "steady", "2")["backlog_p"]


def test_the_beast_ball_price_moves_the_bill(docs):
    def pricey(d):
        for c in d["markets"]["counters"]:
            for it in c["stock"]:
                if it["item"] == "cobblemon:beast_ball":
                    it["price"] = 10000
    w0, w1 = E.World(docs), world_with(docs, pricey)
    b0 = [r for r in E.sinks(w0) if r[0].startswith("Beast")][0]
    b1 = [r for r in E.sinks(w1) if r[0].startswith("Beast")][0]
    assert (b0[1], b0[2]) == (20000, 95000) and (b1[1], b1[2]) == (40000, 190000)


def test_the_income_multiplier_moves_the_income(docs):
    w1 = world_with(docs, lambda d: d["cd"].update(cobbleDollarsIncomeMultiplier=2.5))
    a = run(E.World(docs), ["fighter"], ["design"], runs=50)
    b = run(w1, ["fighter"], ["design"], runs=50)
    ra, rb = stage(a, "design", "fighter", "6")["ledger"]["fights"], stage(b, "design", "fighter", "6")["ledger"]["fights"]
    assert 1.8 < rb / ra < 2.2


# ---------------------------------------------------------------------------------------------------- the loops


def test_the_afk_farmer_cannot_exceed_the_produce_cap(world, docs):
    cap = docs["produce"]["schedule"]["campaign_cap"]
    sim = run(world, ["afk"], ["as_built"], runs=40)
    total = sum(x["ledger"]["produce"] for x in sim["as_built"]["afk"])
    assert total == cap
    assert all(x["idle_hours"] == 6 for x in sim["as_built"]["afk"] if x["stage"].isdigit())


def test_a_pure_fighter_is_short_in_the_early_legs_as_the_design_says(world):
    sim = run(world, ["fighter", "baseline"], ["design"], runs=120, seed=6)
    assert stage(sim, "design", "fighter", "1")["backlog_p"] > 0.3        # known: covered by produce and mining
    assert stage(sim, "design", "baseline", "1")["backlog_p"] < 0.1
    assert stage(sim, "design", "fighter", "8")["backlog_p"] == 0


def test_no_counter_sells_and_no_bank_line_buys_a_dungeon_reward(world):
    lines = [it["item"] for c in world.docs["markets"]["counters"] for it in c["stock"]]
    assert not [i for i in lines if "candy" in i or i.endswith("_gem")]
    assert not [b for b in world.docs["bank"]["buys"] if "candy" in b["item"] or b["item"].endswith("_gem")]


def test_the_report_builds_every_table_and_writes_between_markers(world, tmp_path):
    data, lines = E.build_report(world, runs=12, seed=2, dungeon_runs=150)
    text = "\n".join(lines)
    for n in range(1, 12):
        assert "### T%d." % n in text, n
    assert data["verdicts"] and data["defects"]["design"]["steady"] > 0
    doc = tmp_path / "d.md"
    doc.write_text("head\n<!-- economy_sim:tables:begin -->\nOLD\n<!-- economy_sim:tables:end -->\ntail\n", encoding="utf-8")
    assert E.main(["--runs", "6", "--dungeon-runs", "60", "--write-doc", str(doc)]) == 0
    out = doc.read_text(encoding="utf-8")
    assert out.startswith("head\n") and out.endswith("tail\n") and "OLD" not in out and "### T11." in out
