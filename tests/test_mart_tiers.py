"""The Marts scale with the gyms (the owner's play-test note 9, 2026-10-05): data/traders.json stock_policy.mart.tiers,
tools/traders.py mart_tier / mart_tier_items / mart_shop_items.

Written in the same session as the tiers (the unfinished-items sweep, 2026-10-06): a second reader is wanted.

The tier is the TOWN's, not the player's: every seller is a CobbleDollars merchant whose screen shows one list to every
player (data/markets.json decision counters_are_merchants). So what is asserted is the town-position rule, recomputed
here from data/towns.json with this file's own arithmetic rather than with traders.mart_tiers, plus the shelf a tier
produces and its consistency with the counters.
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import traders as TR  # noqa: E402

DOC = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
TOWNS = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
MARKETS = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
POLICY = DOC["stock_policy"]
MARTS = [r for r in DOC["traders"] if r.get("stock") == "mart"]
TIERS = TR.mart_tiers(DOC, TOWNS)
TIER_ITEMS = {i: t["badges"] for t in POLICY["mart"]["tiers"] for i in t["items"]}
# The Training shelf (stock_policy.mart.training, 2026-10-08): authored lines with their own prices, on the same tier
# rule. Read here from the data, not through traders.training_offers.
TRAINING = {o["item"]: (t["badges"], int(o["price"]))
            for t in (POLICY["mart"].get("training") or {}).get("tiers") or [] for o in t["items"]}

# The shopkeeper template's own offers (bca:stores/store_workers/shopkeeper_ds_general, read from the 2026-10-05
# offline snapshot's COBBLEVERSE-DP-v31.zip): the shelf a tier filters from. Prices are the template's.
TEMPLATE = {"poke_ball": 200, "great_ball": 600, "ultra_ball": 800, "ether": 1000, "max_ether": 2000, "elixir": 3000,
            "max_elixir": 4000, "potion": 200, "super_potion": 700, "hyper_potion": 1500, "revive": 2000,
            "max_potion": 2500, "full_restore": 3000, "max_revive": 4000, "antidote": 100, "paralyze_heal": 200,
            "awakening": 200, "burn_heal": 200, "ice_heal": 200, "full_heal": 400}


def _template_shop():
    return {"CustomName": json.dumps({"text": "General Shopkeeper"}), "CobbleMerchantShop": [
        {"Category": "Stock", "Offers": [{"Item": {"id": "cobblemon:" + k, "count": 1}, "Price": str(v)}
                                          for k, v in TEMPLATE.items()]}]}


def _offered(data):
    return {o["Item"]["id"] for c in data["CobbleMerchantShop"] for o in c["Offers"]}


def _arrival(town_id):
    t = {x["id"]: x for x in TOWNS["towns"]}[town_id]
    return max(0, t["order"] - 1)


# Without it a gym town's Mart sells stock for badges its visitors do not hold yet, or never grows.
def test_a_critical_town_mart_is_tiered_by_the_badges_held_arriving():
    crit = {t["id"] for t in TOWNS["towns"] if t.get("critical_path")}
    seen = 0
    for r in MARTS:
        if r["settlement"] in crit and "mart_tier" not in r:
            assert TIERS[r["id"]] == _arrival(r["settlement"]), r["id"]
            seen += 1
    assert seen == 9, "hometown and the eight gym towns each have one Mart"
    assert TIERS["hometown_mart"] == 0 and TIERS["gym1_mart"] == 0 and TIERS["gym8_mart"] == 7


# Without it an off-path Mart's tier is whatever the code says; recomputed here by its own arithmetic, from where the
# clerk stands (towns.json's Pacifidlog centre is its pre-move site, REVIEW 58).
def test_an_off_path_mart_takes_the_tier_of_the_critical_town_nearest_the_clerk():
    towns = {t["id"]: t for t in TOWNS["towns"]}
    crit = [t for t in TOWNS["towns"] if t.get("critical_path")]
    for r in MARTS:
        if towns[r["settlement"]].get("critical_path") or "mart_tier" in r:
            continue
        c = r["position"]
        near = min(crit, key=lambda t: math.hypot(t["centre"]["x"] - c["x"], t["centre"]["z"] - c["z"]))
        assert TIERS[r["id"]] == max(0, near["order"] - 1), (r["id"], near["id"])
    # the figures the policy's tier_rule states in words
    want = {"tea_mart": 0, "northlight_mart": 5, "mining_mart": 6, "sea_town_mart": 7, "sunset_west_mart": 7}
    assert {k: TIERS[k] for k in want} == want
    for k, v in want.items():
        assert str(v) in POLICY["mart"]["tier_rule"]


# Without it a tier-0 Mart stops being the owner's 2026-09-25 basics, or a tier leaks a later line.
@pytest.mark.parametrize("tier", range(0, 9))
def test_a_mart_at_tier_n_sells_the_basics_and_every_line_up_to_n(tier):
    data, kept, held = TR.apply_stock_policy(_template_shop(), POLICY, "mart", "x", tier)
    want = set(POLICY["mart"]["items"]) | {i for i, b in TIER_ITEMS.items() if b <= tier}
    training = {i for i, (b, _p) in TRAINING.items() if b <= tier}
    assert _offered(data) == want | training and set(kept) == want | training
    assert set(held) == {"cobblemon:" + k for k in TEMPLATE} - want
    cats = {c["Category"] for c in data["CobbleMerchantShop"] if c["Offers"]}
    assert (POLICY["mart"]["training"]["category"] in cats) == bool(training), "the Training category iff a line"


# Without it the shelf is authored, not the template's: prices drift from the template the clerk is read from, or a
# training line from the price the data authors. Clerk "x" is in no early-reach list, so every line is at normal price.
def test_a_tier_line_keeps_the_template_price():
    data, _, _ = TR.apply_stock_policy(_template_shop(), POLICY, "mart", "x", 8)
    seen = 0
    for c in data["CobbleMerchantShop"]:
        for o in c["Offers"]:
            iid = o["Item"]["id"]
            want = TRAINING[iid][1] if iid in TRAINING else TEMPLATE[iid.split(":")[1]]
            assert o["Price"] == str(want), (iid, o["Price"], want)
            seen += iid in TRAINING
    assert seen == len(TRAINING) > 0


# Without it a tier names an item the template never stocks, and the clerk silently lacks it (function mode
# refuses that too, but only against a server's packs).
def test_every_tier_item_is_in_the_mart_template():
    assert {i.split(":")[1] for i in TIER_ITEMS} <= set(TEMPLATE)


# Without it the counter and the Mart sell one thing in one town at two prices: the counter introduces an item, and
# the Mart catches up one town later.
def test_a_mart_never_sells_what_its_own_town_counter_sells():
    by_clerk = {c.get("near_trader"): c for c in MARKETS["counters"] if c.get("near_trader")}
    checked = 0
    for r in MARTS:
        c = by_clerk.get(r["id"])
        if not c:
            continue
        shelf = TR.mart_shop_items(POLICY, r["id"], TIERS[r["id"]])
        both = shelf & {s["item"] for s in c.get("stock") or []}
        assert not both, (r["id"], sorted(both))
        checked += 1
    assert checked >= 13


# Without it the tier ladder and the counters' ladder disagree about when a thing first appears on the road.
def test_an_item_the_counters_sell_enters_the_mart_at_that_counters_badge():
    first = {}
    for c in MARKETS["counters"]:
        if not isinstance(c.get("badge"), int) or c.get("path") != "critical":
            continue
        for s in c.get("stock") or []:
            first[s["item"]] = min(first.get(s["item"], 99), c["badge"])
    shared = set(first) & set(TIER_ITEMS)
    assert shared, "the counters sell some Mart line (super potion, great ball ...)"
    for i in sorted(shared):
        assert TIER_ITEMS[i] == first[i], (i, TIER_ITEMS[i], first[i])


# Without it a later Mart on the road could sell less than an earlier one.
def test_the_critical_path_marts_only_grow():
    order = {t["id"]: t["order"] for t in TOWNS["towns"] if t.get("critical_path")}
    marts = sorted((r for r in MARTS if r["settlement"] in order), key=lambda r: order[r["settlement"]])
    prev = set()
    for r in marts:
        shelf = TR.mart_shop_items(POLICY, None, TIERS[r["id"]])
        assert prev <= shelf, r["id"]
        prev = shelf
    assert "cobblemon:ultra_ball" in prev and "cobblemon:full_restore" not in prev


def test_the_trainer_card_still_rides_on_the_hometown_mart_only():
    assert POLICY["trainer_card"]["item"] in TR.mart_shop_items(POLICY, "hometown_mart", 0)
    assert POLICY["trainer_card"]["item"] not in TR.mart_shop_items(POLICY, "gym8_mart", 7)


# Without it a bad tier table or an unexplained override reaches the generator.
def test_static_rules_refuse_a_bad_tier_table_and_an_unexplained_override():
    doc = copy.deepcopy(DOC)
    doc["stock_policy"]["mart"]["tiers"].append({"badges": 9, "items": ["cobblemon:great_ball", "not_an_id"]})
    msgs = [m for _, m in TR.static_problems(doc)]
    assert any("badges must be 1-8" in m for m in msgs)
    assert any("great_ball is listed twice" in m for m in msgs)
    assert any("not a namespaced item id" in m for m in msgs)
    doc = copy.deepcopy(DOC)
    rec = next(r for r in doc["traders"] if r["id"] == "sunset_west_mart")
    rec["mart_tier"] = 0
    assert any(rid == "sunset_west_mart" and "mart_tier_why" in m for rid, m in TR.static_problems(doc))
    rec["mart_tier_why"] = "walkable from Pallet with no badges"
    assert not [m for rid, m in TR.static_problems(doc) if rid == "sunset_west_mart"]
    assert TR.mart_tiers(doc, TOWNS)["sunset_west_mart"] == 0


def test_the_real_manifest_passes_the_static_rules():
    assert TR.static_problems(DOC) == []


# Without it the summon line carries the basics whatever the tier: the shelf is decided at generation, not in game.
def test_the_summoned_clerk_carries_its_tier_shelf():
    rec = next(r for r in MARTS if r["id"] == "gym4_mart")
    entity = lambda _t: ("cobbledollars:cobble_merchant", _template_shop())
    f = TR.town_functions(rec["settlement"], [rec], entity, POLICY, TIERS)
    line = next(l for l in f["vendors_%s_act" % rec["settlement"]] if l.startswith("summon "))
    assert "cobblemon:great_ball" in line and "cobblemon:super_potion" in line
    assert "cobblemon:ultra_ball" not in line and "cobblemon:full_heal" not in line
    f0 = TR.town_functions(rec["settlement"], [rec], entity, POLICY)          # no tiers: the basics only
    line0 = next(l for l in f0["vendors_%s_act" % rec["settlement"]] if l.startswith("summon "))
    assert "cobblemon:great_ball" not in line0 and "cobblemon:poke_ball" in line0
