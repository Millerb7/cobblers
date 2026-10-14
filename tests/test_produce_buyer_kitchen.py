"""The Trading Post's kitchen and pharmacy goods (data/produce_buyer.json kitchen_pharmacy; tools/produce_buyer.py kp_*).

Written by the implementing session, not by test-author (the brief left no other agent); the independent price audit is
tools/economy_audit.py, which reads these goods as ordinary crates."""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bank as B  # noqa: E402
import produce_buyer as P  # noqa: E402


def _doc():
    return copy.deepcopy(P.load())


def _kp(doc):
    return P.kp_problems(doc, P.wages(), P.notes_of(doc), B.prices(B.load()))[0]


def test_the_kitchen_and_pharmacy_crates_are_the_crafts_rules_derivation():
    # what breaks without it: a raw rate, a recipe or a crate edited by hand moves a price nobody re-derives, and with
    # no cap a price above the cheapest craft route prints money
    assert _kp(_doc()) == []


def test_two_goods_by_hand_arithmetic_not_the_generators():
    # what breaks without it: kp_derive's own arithmetic would be the only thing checking itself. W(early) = $620.
    # bread: three wheat at the crops crate's $20 / 32 = $0.625 each = $1.875, plus the step max($2, 1%) = $2: $3.875 a
    # bread, a crate of 4 is $15.50, rounded DOWN to $15. cookie: eight to the craft, two wheat and a cocoa bean (a
    # 'harvest' unit, 620 / 1000 = $0.62): $1.87 + $2 = $3.87 / 8 = $0.484 each, a crate of 32 is $15.48, down to $15.
    doc = _doc()
    crates = {c["items"][0]: c for c in doc["crates"] if c.get("kp")}
    wage = P.wages()
    assert (crates["minecraft:bread"]["count"], P.crate_price(crates["minecraft:bread"], wage)) == (4, 15)
    assert (crates["minecraft:cookie"]["count"], P.crate_price(crates["minecraft:cookie"], wage)) == (32, 15)


def test_a_kitchen_crate_edited_off_its_derivation_is_named():
    doc = _doc()
    next(c for c in doc["crates"] if c.get("id") == "kp_bread")["rate_per_hour"] = 100
    assert any("kitchen_pharmacy minecraft:bread" in p for p in _kp(doc))


def test_a_good_with_no_priced_route_is_refused_not_guessed():
    # what breaks without it: tasty_tail has no recipe and no live dropper; a price would have no derivation
    doc = _doc()
    doc["kitchen_pharmacy"]["sold"].append("cobblemon:tasty_tail")
    assert any("tasty_tail" in p and "no recipe" in p for p in _kp(doc))


def test_a_good_is_never_in_two_channels():
    doc = _doc()
    sold = set(doc["kitchen_pharmacy"]["sold"])
    others = {i for c in doc["crates"] if not c.get("kp") for i in c["items"]} | set(doc["specimens"]["items"])
    assert not (sold & others)
    assert not (sold & set(doc["never_sold"]["ids"]))
    assert not (sold & set(doc["kitchen_pharmacy"]["not_sold"]))
