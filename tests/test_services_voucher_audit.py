"""Independent audit of 8a2e911: the services' price rule, services against craft routes, and the Challenge voucher.

Written by the test author, not the builder. Expectations come from sources the builder's tools do not use for the
same number:
  - the fight hour from the rosters through tools/income_model.py measure() (not data/markets.json income_basis);
  - EV yields from the Cobblemon jar's own tooltips and recipes from the jars (economy_audit's reader);
  - input prices from every emitted shelf and counter (economy_audit's cheapest(), reading the snapshot's templates);
  - the voucher's kit value from modpack/config/cobbledollars/bank.json (the file the server runs), not bank.prices().
Mutation tests change the GENERATOR (tools/training_services.py, tools/income_model.py, tools/challenge_voucher.py),
never data/.

NOT COVERED (needs a running server or an experiment): that the services charge what the data says in game; that one
brewing-stand ingredient serves three bottles (vanilla, ASSUMED for Cobblemon's recipe type); that berry plants regrow
(the craft routes count a berry once per stat); the hours_saved = 1 assumption itself (an EXP timing); that a
Challenge grant is ever paid (nothing grants the voucher yet: BUILD LIST U6).
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

SERVICES = json.loads((ROOT / "data" / "training_services.json").read_text(encoding="utf-8"))
BANK_DOC = json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8"))
MARKETS = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
CHALLENGE = json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))
EMITTED_BANK = {e["item"]: int(e["price"]) for e in json.loads(
    (ROOT / "modpack" / "config" / "cobbledollars" / "bank.json").read_text(encoding="utf-8"))["bank"]}


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


@pytest.fixture(scope="module")
def legs():
    """{leg: (normal, challenge)} income, from the rosters (income_model.measure), not from data/markets.json."""
    m = I.measure()
    n, _ = I.totals(m, "normal")
    c, _ = I.totals(m, "challenge")
    return {k: (n[k], c[k]) for k in n}


def strictly_above(x, step):
    return (math.floor(x / step) + 1) * step


def rule_expectation(leg_income):
    """The price the owner's rule gives: the smallest $100 multiple strictly above one hour saved x the fight hour."""
    hour = Fraction(round(leg_income)) / Fraction(BANK_DOC["effort_model"]["max_leg_hours"])
    return strictly_above(hour, 100)


# ============================================================================================ the price rule
# Without it the EV and IV prices could drift from "one hour of the richest badge leg's fighting": the expectation is
# re-derived from the rosters (leg 8 is the largest of the eight badge legs, 68,505 / 4 = 17,126.25 -> $17,200).
def test_the_ev_and_iv_prices_are_one_richest_leg_fight_hour_from_the_rosters(legs):
    badge = {k: v[0] for k, v in legs.items() if isinstance(k, int)}
    assert sorted(badge) == list(range(1, 9))
    richest = max(badge, key=badge.get)
    assert richest == SERVICES["price_rule"]["anchor_badge"] == 8
    want = rule_expectation(badge[8])
    assert want == 17200
    assert SERVICES["services"]["ev"]["price"] == want
    assert SERVICES["services"]["iv"]["price_per_stat"] == want
    assert T.price_rule_problems(SERVICES) == []


# Without it the services' audit could be a rubber stamp: tools/training_services.py's rule with "strictly above"
# turned into "at or below" (floor) or reading leg 7 must name the real prices as wrong; the data is untouched.
@pytest.mark.parametrize("why,old,new", [
    ("floor instead of strictly above", '// step + 1) * step', '// step) * step'),
    ("the leg before the anchor", 'leg_by_badge"][str(r["anchor_badge"])]', 'leg_by_badge"][str(r["anchor_badge"] - 1)]'),
])
def test_a_mutated_price_rule_names_the_real_prices(why, old, new):
    m = mutant("training_services", (old, new))
    probs = m.price_rule_problems(SERVICES)
    assert any(p.startswith("services.ev.price is $17200") for p in probs), (why, probs)
    assert any(p.startswith("services.iv.price_per_stat is $17200") for p in probs), (why, probs)


# Without it this file's own expectation could secretly be data/markets.json: an income model paying 10% more per
# battle (the GENERATOR mutated) moves the independent price off $17,200, so the data's price would fail here.
def test_the_independent_expectation_follows_the_income_model_not_the_record():
    m = mutant("income_model", ("* Fraction(9, 4) * Fraction(mult))", "* Fraction(9, 4) * Fraction(mult) * Fraction(11, 10))"))
    n, _ = m.totals(m.measure(), "normal")
    assert rule_expectation(n[8]) != SERVICES["services"]["ev"]["price"]


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
    """[EVs per stat] of the largest spread the EV service sells."""
    spreads = SERVICES["services"]["ev"]["spreads"]
    big = max(spreads, key=lambda s: sum(s["evs"].values()))
    return sorted(big["evs"].values(), reverse=True)


# Without it the "crafting is the route" decision could invert unseen: every craft route to one EV spread must cost
# fewer dollars than the service, counting each input at its cheapest seller per use (a berry once per stat: the plant
# regrows, ASSUMED), and an input with no seller must be farmable or a gathered material. Measured 2026-10-08:
# vitamins $2,800, mochi $9,500, feathers $10,200, two Mart power items $3,000, against $17,200.
@needs_jars
def test_no_ev_craft_route_costs_more_dollars_than_the_service(market):
    best, farm, evs = market
    assert evs["cobblemon:hp_up"] == 10 and evs["cobblemon:health_mochi"] == 4
    assert evs["cobblemon:health_feather"] == 1 and evs["cobblemon:power_weight"] == 8
    need = _spread_ev_need()
    price = SERVICES["services"]["ev"]["price"]

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
    routes = {"vitamins": vitamins, "mochi": mochi, "feathers": feathers, "power items": power}
    assert routes == {"vitamins": 2800, "mochi": 9500, "feathers": 10200, "power items": 3000}, routes
    assert all(v < price for v in routes.values()), routes


# Without it a shelf could undercut the service: the finished items for one spread, bought outright with no effort,
# must cost more than the service, or nobody would pay for it (shelf vitamins 53 x $3,500, mochi 127 x $800).
@needs_jars
def test_no_shelf_sells_a_spread_for_less_than_the_service(market):
    best, _farm, evs = market
    need = _spread_ev_need()
    price = SERVICES["services"]["ev"]["price"]
    for item in ("cobblemon:hp_up", "cobblemon:health_mochi", "cobblemon:health_feather"):
        if item not in best:
            continue
        n = sum(math.ceil(x / evs[item]) for x in need)
        assert n * best[item][0] > price, (item, n, best[item])


# Without it a bottle cap on some shelf could undercut the IV service: no seller sells a cap of any kind, so the
# only routes to a perfect IV are fished caps (no dollars) and the $17,200 a stat service.
@needs_jars
def test_no_bottle_cap_is_sold_for_less_than_the_iv_service(market):
    best, _farm, _evs = market
    price = SERVICES["services"]["iv"]["price_per_stat"]
    caps = {i: b for i, b in best.items() if i.startswith("obc:bottle_cap")}
    assert all(b[0] >= price for b in caps.values()), caps


# ============================================================================================ the Challenge voucher
def _mart_power_prices():
    shelf = {}
    for tier in json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))["stock_policy"]["mart"]["training"]["tiers"]:
        for it in tier["items"]:
            shelf[it["item"]] = int(it["price"])
    return shelf


def voucher_problems(c, legs_income, cdoc=CHALLENGE):
    """Every way `c` (a computed voucher block) breaks the owner's shape, judged from independent sources."""
    v = cdoc["voucher"]
    out = []
    gated = [int(l["price"]) for r in MARKETS["counters"] for l in r.get("stock") or [] if l.get("price_rule") == "income_gate"]
    oak = (min(gated) - 1) // 100 * 100
    kits = {}
    for k in v["kits"]:
        kits[k["for_leg"]] = sum(EMITTED_BANK[i] * n for part in ("tm", "held", "extra") for i, n in (k.get(part) or {}).items())
    shelf = _mart_power_prices()
    power = sum(shelf[i] for i in v["power_kit"]["items"])
    total = oak + sum(kits.values()) + power
    s = c["schedule"]
    if c["total"] != total:
        out.append("total %d, independently %d (Oak %d + kits %d + power kit %d)" % (c["total"], total, oak,
                                                                                    sum(kits.values()), power))
    if sum(g["value"] for g in s) != total:
        out.append("the grants sum to %d, not the total %d" % (sum(g["value"] for g in s), total))
    if s[0]["at"] != "oak_mode_choice" or s[0]["value"] != oak or s[0]["kits"]:
        out.append("Oak's grant is not $%d cash" % oak)
    gyms = s[1:]
    if [g["at"] for g in gyms] != ["gym%d_cleared" % n for n in range(1, 9)]:
        out.append("the gym grants are not gyms 1-8 in order")
    vals = [g["value"] for g in gyms]
    if any(b > a for a, b in zip(vals, vals[1:])):
        out.append("not front-loaded: %s" % vals)
    seen = []
    for i, g in enumerate(s):
        if g["cash"] < 0 or g["value"] != g["cash"] + sum(kits[k] for k in g["kits"]):
            out.append("%s: value %d is not cash %d + its kits" % (g["at"], g["value"], g["cash"]))
        for k in g["kits"]:
            seen.append(k)
            if i > k - 1:
                out.append("the kit for leg %d arrives at %s, after gym %d" % (k, g["at"], k - 1))
    if sorted(seen) != sorted(kits):
        out.append("kits delivered %s, not each of %s once" % (sorted(seen), sorted(kits)))
    # inverse to the Challenge income each grant opens, from the rosters: gym n opens leg n+1, gym 8 VR + the League
    opens = [legs_income[n + 1][1] for n in range(1, 8)] + [legs_income["vr"][1] + legs_income["league"][1]]
    w = [1 / x for x in opens]
    rest = total - oak
    for n, (g, wi) in enumerate(zip(gyms, w), 1):
        ideal = rest * wi / sum(w)
        slack = 50 * 8 if n == 1 else 50          # each grant rounds down to $50; gym 1 takes the remainder
        if not (ideal - slack <= g["value"] <= ideal + slack):
            out.append("gym %d grant %d, inverse-income share %.0f" % (n, g["value"], ideal))
    return out


# Without it the voucher could drift from the owner's shape: the committed schedule, judged from the rosters, the
# emitted bank and the Mart shelf, sums to its total ($23,748), pays Oak $4,000 cash, never grows after gym 1, follows
# the inverse Challenge income, and puts every kit in hand by the gym before the leg it answers.
def test_the_committed_voucher_keeps_the_owners_shape(legs):
    c = CHALLENGE["voucher"]["computed"]
    assert voucher_problems(c, legs) == []
    assert c["total"] == 23748
    assert CV.compute() == c          # the committed block is the tool's output (its --check)


# Without it voucher_problems could pass anything: each mutation of tools/challenge_voucher.py (data untouched) that
# slips past the tool's own guards must be named here.
@pytest.mark.parametrize("why,old,new", [
    ("the rounding remainder dropped", "vals[0] += rest - sum(vals)", "vals[0] += 0"),
    ("kits valued at half", "total += prices[item] * int(n)", "total += prices[item] * int(n) // 2"),
    ("a power item left out", "return sum(have[i] for i in want)", "return sum(have[i] for i in want[1:])"),
    ("weighted by the Normal income", 'ch = markets["income_basis"]["challenge"]["leg_by_badge"]',
     'ch = markets["income_basis"]["leg_by_badge"]'),
])
def test_a_mutated_voucher_generator_is_named(legs, why, old, new):
    m = mutant("challenge_voucher", (old, new))
    try:
        c = m.compute()
    except SystemExit as e:
        pytest.fail("the mutant tripped the tool's own guard, so it does not test this check: %s (%s)" % (why, e))
    assert voucher_problems(c, legs), why


def _liquidation(mats, conv):
    """Dollars a bundle of materials can be turned into at the emitted bank, each unit by itself or by one
    single-input furnace or crafting conversion of it (multi-input crafts such as the netherite ingot are NOT
    counted: 4 scrap + 4 gold at bank value is $888 against the ingot's $900, a further $12 an ingot)."""
    unit = {}
    for m in mats:
        best = EMITTED_BANK.get(m, 0)
        for _name, _kind, ings, rid, rc in conv:
            if len(ings) == 1 and m in ings[0][0] and rid in EMITTED_BANK:
                best = max(best, EMITTED_BANK[rid] * rc / ings[0][1])
        unit[m] = best
    return sum(unit[m] * n for m, n in mats.items())


# DEFECT (recorded, not fixed): a grant can be sold back for more than the voucher says it is worth. The kits are
# valued at the bank's price for each material as given, but raw iron smelts to an iron ingot the bank buys for $9
# against raw iron's $8 (data/bank.json; minecraft:iron_ingot_from_smelting_raw_iron in the vanilla jar). The gym-1
# grant's 344 raw iron liquidate $344 above its $7,298, gym 2's 64 another $64. Small, but the voucher's total is not
# what it pays. Fix is the tool's valuation or the kits (data/challenge_mode.json), not this test.
# strict: when no grant liquidates above its value, this xfail fails and the marker goes.
@needs_jars
@pytest.mark.xfail(strict=True, reason="raw iron in the kits smelts to a $9 ingot against its $8 valuation")
def test_no_grant_sells_back_for_more_than_its_value():
    conv = E.load_jars(SNAP, VANILLA).conversions()
    kits = {k["for_leg"]: k for k in CHALLENGE["voucher"]["kits"]}
    over = []
    for g in CHALLENGE["voucher"]["computed"]["schedule"]:
        mats = {}
        for leg in g["kits"]:
            for part in ("tm", "held", "extra"):
                for i, n in (kits[leg].get(part) or {}).items():
                    mats[i] = mats.get(i, 0) + n
        got = g["cash"] + _liquidation(mats, conv)
        if got > g["value"]:
            over.append("%s: worth %d, sells for %.0f" % (g["at"], g["value"], got))
    assert not over, over
