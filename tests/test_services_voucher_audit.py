"""Independent audit of the services' price rule, services against craft routes, and the Challenge voucher.

Rewritten 2026-10-22 for the owner's changed rules, each cited where it bites:
  - the owner, 2026-10-21: service prices RISE WITH BADGES (the 2026-10-10 rule, "a service is the convenience that
    costs more than the play it saves", one leg-8 fight hour = $17,200, is reversed for the three services);
  - the owner, 2026-10-21: "so far no one is doing optional fights just the gym trainers and leaders": prices read
    the PATH income (data/markets.json income_basis.path), not the road's;
  - the owner, 2026-10-22: "i dont see enough cushion for challenge players, they should have it easier": the voucher
    covers a team's training and two answer TMs per badge, x1.5 (data/challenge_mode.json voucher.rule).
This session also built what it audits (one session did both; CLAUDE.md asks for different agents: a test-author pass
over this file is owed).

Expectations come from sources the builder's tools do not use for the same number:
  - the path income from the rosters through tools/income_model.py measure()'s per-battle level sums, with WHICH
    battles count decided here from the seat files' eye_contact and the row kind, not from the tool's on_path;
  - EV yields from the Cobblemon jar's own tooltips and recipes from the jars (economy_audit's reader);
  - the TM shelf's tier price from the committed counter lines' own prices, not from tools/markets.py's rule.
Mutation tests change the GENERATOR (tools/training_services.py, tools/income_model.py, tools/challenge_voucher.py),
never data/.

NOT COVERED (needs a running server or an experiment): that the services charge what the data says in game; that a
grant is paid; that one brewing-stand ingredient serves three bottles; learnsets of the answer TMs.
"""
from __future__ import annotations

import json
import math
import re
import sys
import types
import zipfile
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import economy_audit as E  # noqa: E402
import income_model as I  # noqa: E402
import training_services as T  # noqa: E402
import challenge_voucher as CV  # noqa: E402

SNAP = E.default_server_dir()
VANILLA = E.default_vanilla_jar()
HAVE_SNAP = bool(SNAP) and Path(SNAP).is_dir()
HAVE_JARS = HAVE_SNAP and bool(VANILLA) and Path(VANILLA).is_file()
needs_jars = pytest.mark.skipif(not HAVE_JARS, reason="no snapshot + vanilla jar (COBBLERS_SNAPSHOT_DIR)")


def _j(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


SERVICES = _j("data/training_services.json")
MARKETS = _j("data/markets.json")
CHALLENGE = _j("data/challenge_mode.json")
QUESTS = _j("data/quests.json")
TIERS = range(0, 9)
PAYOUT = Fraction(9, 32)          # 0.28125 S^2 a win, CobbleDollars battleVictory at multiplier 1.25


def mutant(name, *pairs):
    """tools/<name>.py with each (old, new) applied once to its SOURCE, loaded as a fresh module; the file is untouched."""
    path = ROOT / "tools" / ("%s.py" % name)
    src = path.read_text(encoding="utf-8")
    for a, b in pairs:
        assert src.count(a) == 1, "the mutation target moved in tools/%s.py: %r" % (name, a)
        src = src.replace(a, b)
    mod = types.ModuleType("%s_mutant" % name)
    mod.__file__ = str(path)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


def eyes():
    """{trainer id: eye_contact} read here from the four seat files."""
    out = {}
    for rel in ("data/route_trainers.json", "data/late_route_trainers.json", "data/vr_trainers.json",
                "data/gym_junior_trainers.json"):
        for s in _j(rel)["trainers"]:
            out[s["id"]] = s.get("eye_contact") is True
    return out


def forced(row, ey):
    """The path's battles, in this file's words: the leader, and a route/VR/junior trainer that has eye contact."""
    return row["kind"] == "leader" or (row["kind"] in ("route", "junior") and ey.get(row["id"]) is True)


@pytest.fixture(scope="module")
def path_legs():
    """{badges held: (normal, challenge) path income of the leg played}, from the rosters' level sums."""
    m = I.measure()
    ey = eyes()
    order = [1, 2, 3, 4, 5, 6, 7, 8, "vr"]
    legs = {L["leg"]: L["trainers"] for L in m["legs"]}
    out = {}
    for held, leg in enumerate(order):
        rows = [r for r in legs[leg] if forced(r, ey)]
        out[held] = tuple(float(sum(PAYOUT * r[mode]["S"] ** 2 for r in rows)) for mode in ("normal", "challenge"))
    return out


def up(x, step):
    return int(math.ceil(Fraction(x) / step)) * step


# ============================================================================================ the path income
# Without it the path figure every price reads could drift from what the path actually pays: re-summed here from the
# rosters with this file's own reading of which fights are forced, it must equal data/markets.json income_basis.path,
# and it must be what ECONOMY_V3.md section 2 measured by hand (leg 1 $1,932 ... Victory Road $49,341).
def test_the_path_income_is_the_forced_fights_from_the_rosters(path_legs):
    got = MARKETS["income_basis"]["path"]["leg_by_badges_held"]
    assert {int(k): v for k, v in got.items()} == {t: int(round(path_legs[t][0])) for t in TIERS}
    ch = MARKETS["income_basis"]["path"]["challenge"]["leg_by_badges_held"]
    assert {int(k): v for k, v in ch.items()} == {t: int(round(path_legs[t][1])) for t in TIERS}
    assert [int(round(path_legs[t][0])) for t in TIERS] == [1932, 2468, 6210, 8619, 15443, 21471, 26734, 41026, 49341]


# Without it a mutated income model (the mansion counted as forced) could write a path figure nobody re-derives.
def test_a_mutated_path_rule_moves_off_the_independent_figure(path_legs):
    m = mutant("income_model", ('    if kind in ("leader", "league"):\n        return True',
                                '    if kind in ("leader", "league", "mansion"):\n        return True'))
    block = m.path_block(m.measure())
    assert block["leg_by_badges_held"]["0"] != int(round(path_legs[0][0]))


# ============================================================================================ the price rule
def _rule(key, t, path_legs):
    frac = {"raise": "0.05", "ev": "0.15", "iv": "0.025"}[key]
    assert str(SERVICES["price_rule"]["fractions"][T.RULE_FIELDS[key][0]]) == frac
    return up(Fraction(frac) * Fraction(round(path_legs[t][0])), 100)


# Without it a service could be priced flat again, or off the path: every tier of every service is the rule's price
# (the owner, 2026-10-21: RISES WITH BADGES), re-derived here, and the table is ECONOMY_V3.md 3.2's (tiers 1-8) with
# tier 0 by the same rule. A re-measured income has to move these on purpose.
def test_every_service_tier_is_its_share_of_the_path_leg(path_legs):
    s = SERVICES["services"]
    for key, field in (("raise", "price_by_tier"), ("ev", "price_by_tier"), ("iv", "price_per_stat_by_tier")):
        assert {int(t): v for t, v in s[key][field].items()} == {t: _rule(key, t, path_legs) for t in TIERS}, key
    assert [s["raise"]["price_by_tier"][str(t)] for t in TIERS] == [100, 200, 400, 500, 800, 1100, 1400, 2100, 2500]
    assert [s["ev"]["price_by_tier"][str(t)] for t in TIERS] == [300, 400, 1000, 1300, 2400, 3300, 4100, 6200, 7500]
    assert [s["iv"]["price_per_stat_by_tier"][str(t)] for t in TIERS] == [100, 100, 200, 300, 400, 600, 700, 1100, 1300]
    assert T.price_rule_problems(SERVICES) == []


# Without it the services' audit could be a rubber stamp: tools/training_services.py's rule rounded down, or read from
# the road's leg instead of the path's, must name the real prices as wrong; the data is untouched.
@pytest.mark.parametrize("why,old,new", [
    ("rounded down", "return int(-(-want // step)) * step", "return int(want // step) * step"),
    ("the road's leg", 'markets["income_basis"]["path"]["leg_by_badges_held"][str(t)]',
     'markets["income_basis"]["leg_by_badge"][str(max(t, 1))]'),
])
def test_a_mutated_price_rule_names_the_real_prices(why, old, new):
    m = mutant("training_services", (old, new))
    probs = m.price_rule_problems(SERVICES)
    assert any(p.startswith("services.ev.price_by_tier") for p in probs), (why, probs)


# ===================================================================================== services against craft routes
def _tooltip_evs(jar):
    """{item: EVs per use} from the Cobblemon jar's en_us tooltips ('Raises the Pokemon's HP EVs by 10')."""
    lang = json.loads(zipfile.ZipFile(jar).read("assets/cobblemon/lang/en_us.json").decode("utf-8"))
    out = {}
    for k, v in lang.items():
        m = re.fullmatch(r"item\.cobblemon\.([a-z_]+)\.tooltip", k)
        g = re.search(r"EVs by (\d+)$", v) or re.search(r"Grants (\d+) \w+ EVs when gaining experience", v)
        if m and g:
            out["cobblemon:" + m.group(1)] = int(g.group(1))
    return out


@pytest.fixture(scope="module")
def market():
    """(best {item: (unit $, how)} over every sited sale and jar recipe, the AFK farm set, the EV tooltips)."""
    jars = E.load_jars(SNAP, VANILLA)
    conv = jars.conversions()
    sales = E.market_sales() + E.apricorn_sales() + E.default_shop_sales() + E.trader_sales(SNAP)[0]
    farm, _b = E.afk_farmable(jars, SNAP, conv)
    cobblemon = next(Path(SNAP, "mods").glob("Cobblemon-fabric-*.jar"))
    return E.cheapest(sales, conv), farm, _tooltip_evs(cobblemon)


def _spread_ev_need():
    spreads = SERVICES["services"]["ev"]["spreads"]
    big = max(spreads, key=lambda s: sum(s["evs"].values()))
    return sorted(big["evs"].values(), reverse=True)


def _top(key):
    s = SERVICES["services"][key]
    return max((s["price_per_stat_by_tier"] if key == "iv" else s["price_by_tier"]).values())


# REWRITTEN 2026-10-22. Until then this asserted every craft route to one EV spread cost FEWER dollars than the
# service (the 2026-10-10 rule: the service costs more than the play it saves). The owner reversed that on 2026-10-21
# (prices rise with badges, cheap early), so the service now undercuts the routes early on purpose: it sells time,
# and EV power was always free by battle. What still holds, and what this protects: the routes are what the jars and
# the shelves say (measured 2026-10-08: vitamins $2,800, mochi $9,500, feathers $10,200, two Mart power items $3,000),
# and every route is still OPEN (an input with no seller is farmable or gathered), so the service is never the only way.
@needs_jars
def test_every_ev_craft_route_is_measured_and_open(market):
    best, farm, evs = market
    assert evs["cobblemon:hp_up"] == 10 and evs["cobblemon:health_mochi"] == 4
    assert evs["cobblemon:health_feather"] == 1 and evs["cobblemon:power_weight"] == 8
    need = _spread_ev_need()

    def per_use(item):
        if item in best:
            return best[item][0]
        assert item in farm, "%s has no seller and no farm: the route needs a gathered input" % item
        return 0.0

    def once(item):
        return best[item][0] if item in best else 0.0

    berry = "cobblemon:pomeg_berry"
    batches = sum(math.ceil(math.ceil(n / evs["cobblemon:hp_up"]) / 3) for n in need)
    vitamins = batches * (per_use("cobblemon:medicinal_leek") + per_use("cobblemon:vivichoke")) + len(need) * once(berry)
    crafts = sum(math.ceil(math.ceil(n / evs["cobblemon:health_mochi"]) / 3) for n in need)
    mochi = crafts * (per_use("minecraft:honey_bottle") + per_use("cobblemon:hearty_grains")) + len(need) * once(berry)
    feather_crafts = sum(math.ceil(n / (3 * evs["cobblemon:health_feather"])) for n in need)
    feathers = feather_crafts * 3 * per_use("minecraft:feather")
    power = 2 * best["cobblemon:power_bracer"][0]
    assert {"vitamins": vitamins, "mochi": mochi, "feathers": feathers, "power items": power} == \
        {"vitamins": 2800, "mochi": 9500, "feathers": 10200, "power items": 3000}


# Without it a shelf could undercut the service at some tier: the finished items for one spread, bought outright with
# no effort, must cost more than the service at its DEAREST tier (shelf vitamins 53 x $3,500, mochi 127 x $800), so
# the shelf ordering ECONOMY_V3.md 3.2 keeps holds at every badge.
@needs_jars
def test_no_shelf_sells_a_spread_for_less_than_the_service_at_any_tier(market):
    best, _farm, evs = market
    need = _spread_ev_need()
    for item in ("cobblemon:hp_up", "cobblemon:health_mochi", "cobblemon:health_feather"):
        if item not in best:
            continue
        n = sum(math.ceil(x / evs[item]) for x in need)
        assert n * best[item][0] > _top("ev"), (item, n, best[item])


# Without it a bottle cap on some shelf could undercut the IV service at some tier.
@needs_jars
def test_no_bottle_cap_is_sold_for_less_than_the_iv_service_at_any_tier(market):
    best, _farm, _evs = market
    caps = {i: b for i, b in best.items() if i.startswith("obc:bottle_cap")}
    assert all(b[0] >= _top("iv") for b in caps.values()), caps


# ============================================================================================ the Challenge voucher
def shelf_tm_unit():
    """{tier: one TM's price} from the committed tm_tier counter lines' own prices; every line of a tier agrees."""
    out = {}
    for c in MARKETS["counters"]:
        for it in c.get("stock") or []:
            if it.get("price_rule") == "tm_tier" and it.get("answers"):
                out.setdefault(it["tier"], set()).add(it["price"] // (it.get("count") or 1))
    assert all(len(v) == 1 for v in out.values()), out
    return {t: v.pop() for t, v in out.items()}


def voucher_problems(c):
    """Every way `c` (a computed voucher block) breaks the owner's 2026-10-22 rule, judged from the data's prices."""
    out = []
    s = SERVICES["services"]
    tm = shelf_tm_unit()
    want_at = ["oak_mode_choice"] + ["gym%d_cleared" % n for n in range(1, 9)]
    if [g["at"] for g in c["schedule"]] != want_at:
        out.append("the steps are %s" % [g["at"] for g in c["schedule"]])
        return out
    total = 0
    for t, g in enumerate(c["schedule"]):
        one = s["raise"]["price_by_tier"][str(t)] + s["ev"]["price_by_tier"][str(t)] \
            + 6 * s["iv"]["price_per_stat_by_tier"][str(t)]
        basket = 6 * one + 2 * tm.get(t, 0)
        want = up(Fraction(3, 2) * basket, 50)
        total += want
        if (g["basket"], g["value"], g["cash"]) != (basket, want, want):
            out.append("%s: basket %s value %s cash %s, independently %d -> %d" % (g["at"], g["basket"], g["value"],
                                                                                g["cash"], basket, want))
    if c["total"] != total:
        out.append("total %d, independently %d" % (c["total"], total))
    return out


# Without it the voucher could drift from the owner's 2026-10-22 rule ("they should have it easier"): each grant
# covers, at the prices of the badge it opens, six Pokemon's raise + EV spread + six IVs and two answer TMs, x1.5;
# Oak's is the first leg's (tier 0, where no shelf sells TMs). Replaces the 2026-10-10 front-loaded $23,748.
def test_the_committed_voucher_keeps_the_owners_rule():
    c = CHALLENGE["voucher"]["computed"]
    assert voucher_problems(c) == []
    assert [g["value"] for g in c["schedule"]] == [9000, 13500, 30000, 41700, 66900, 94800, 115500, 177300, 212100]
    assert c["total"] == 760800
    assert CV.compute() == c          # the committed block is the tool's output (its --check)
    oak = [e for q in QUESTS["quests"] for t in q.get("transitions") or [] for e in t.get("effects") or []
           if e.get("kind") == "challenge_voucher"]
    assert [(e["at"], e["cash"]) for e in oak] == [("oak_mode_choice", 9000)]


# Without it voucher_problems could pass anything: each mutation of tools/challenge_voucher.py (data untouched) must be
# named here.
@pytest.mark.parametrize("why,old,new", [
    ("the multiplier ignored", 'mult = Fraction(str(rule["multiplier"]))\n    step', 'mult = Fraction(1)\n    step'),
    ("a team of five", 'team, tms = int(rule["team"]), int(rule["answer_tms"])',
     'team, tms = int(rule["team"]) - 1, int(rule["answer_tms"])'),
    ("the TMs never counted", "return (n * M.tm_tier_unit(markets, t), len(answers)) if answers else (0, 0)",
     "return (0, 0)"),
    ("one IV, not six", '+ 6 * int(s["iv"]["price_per_stat_by_tier"][str(t)])', '+ int(s["iv"]["price_per_stat_by_tier"][str(t)])'),
])
def test_a_mutated_voucher_generator_is_named(why, old, new):
    m = mutant("challenge_voucher", (old, new))
    assert voucher_problems(m.compute()), why

# Removed 2026-10-22: test_no_grant_sells_back_for_more_than_its_value (a strict xfail: the gym-1 kit's raw iron
# smelted to a $9 ingot against its $8 valuation). Every grant has been cash since the owner's 2026-10-21 "just give
# him money", and the kit valuation is superseded (data/challenge_mode.json voucher.superseded_kits_basis), so no
# grant carries a material to sell back.
