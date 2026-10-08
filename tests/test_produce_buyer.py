"""tools/produce_buyer.py, the generator's own tests (data/produce_buyer.json; ECONOMY_OVERHAUL U2).

The independent audit is test-author's tools/produce_buyer_audit.py; these hold the generator to its own rules."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bank as B  # noqa: E402
import produce_buyer as P  # noqa: E402

FLAGS = {"gym%d_cleared" % i for i in range(1, 9)}


def _doc():
    return copy.deepcopy(P.load())


def _static(doc, bank=None, pts=()):
    return P.static_problems(doc, FLAGS, B.prices(B.load()) if bank is None else bank, list(pts))


def test_the_schedule_is_the_designs_table():
    doc = _doc()
    assert [P.schedule_at(doc, b) for b in range(9)] == [(40, 40), (30, 30), (25, 20), (20, 10), (10, 10), (10, 10),
                                                         (10, 10), (10, 10), (0, 0)]
    assert P.campaign_total(doc) == 3600 == doc["schedule"]["campaign_cap"]


def test_the_committed_data_and_output_pass():
    doc = _doc()
    assert _static(doc) == []
    assert P.output_problems(doc, P.build(doc)) == []


def test_a_rising_price_or_a_gap_is_refused():
    doc = _doc()
    doc["schedule"]["rows"][2]["price"] = 35
    assert any("the price rises" in p for p in _static(doc))
    doc = _doc()
    doc["schedule"]["rows"][4]["badges"] = [4, 6]
    assert any("not 0..8 once each" in p for p in _static(doc))


def test_a_crate_item_the_bank_still_buys_is_refused():
    doc = _doc()
    probs = _static(doc, bank={"minecraft:melon_slice": 5})
    assert any("the bank still buys minecraft:melon_slice" in p for p in probs), probs


def test_a_seller_at_or_under_the_crates_unit_is_refused():
    doc = _doc()
    probs = _static(doc, pts=[("a stall", "minecraft:cod", 2.5)])   # fish: 16 a crate at $40 top = $2.50 a unit
    assert any("sells minecraft:cod at $2.5" in p for p in probs), probs
    assert _static(doc, pts=[("a stall", "minecraft:cod", 2.51)]) == []


def test_an_unplanned_badge_flag_is_refused():
    doc = _doc()
    doc["badge_flags"][0] = "gym1_beaten"
    assert any("gym1_beaten" in p for p in _static(doc))


def test_every_sale_counts_takes_pays_and_verifies_in_that_order():
    doc = _doc()
    files = P.build(doc)
    rel = P.fn_path("sell/crops")
    body = files[rel]
    i_take = next(i for i, ln in enumerate(body) if ln.endswith("clear @s #cobblers:produce_buyer/crops 32"))
    i_pay = next(i for i, ln in enumerate(body) if ln.startswith("function cobblers:produce_buyer/pay"))
    swapped = list(body)
    swapped[i_take], swapped[i_pay] = swapped[i_pay], swapped[i_take]
    files[rel] = swapped
    assert any(p.startswith("crate crops: the sale is not count < take") for p in P.output_problems(doc, files))
    files = P.build(doc)
    files[rel] = [ln for ln in body if "#after" not in ln]
    assert any(p.startswith("crate crops") for p in P.output_problems(doc, files))
    files = P.build(doc)
    files[rel] = body + ["cobbledollars give @s 40"]
    assert any("outside the pay macro" in p for p in P.output_problems(doc, files))


def test_the_leg_reads_every_badge_flag_and_resets_on_a_changed_count():
    doc = _doc()
    leg = P.leg_lines(doc)
    for f in sorted(FLAGS):
        assert any("advancements={cobblers:flag/%s=true}" % f in ln for ln in leg), f
    assert "execute unless score @s cob_pb_leg = #badges cob_pb run scoreboard players set @s cob_pb_sold 0" in leg
    assert "execute if score #badges cob_pb matches 4..7 run scoreboard players set #price cob_pb 10" in leg


def test_the_pack_ships_its_tags_and_one_option_per_crate():
    doc = _doc()
    files = P.build(doc)
    assert files["data/cobblers/tags/item/produce_buyer/crops.json"]["values"] == doc["crates"][0]["items"]
    dlg = json.dumps(files["data/cobblers/dialogues/dlg_produce_buyer_hollin_farm.json"])
    for c in doc["crates"]:
        assert "function cobblers:produce_buyer/sell/%s" % c["id"] in dlg
    assert "cobblers:produce_buyer/pay" in "\n".join(files[P.fn_path("sell/fish")])


def _ground():
    import ground as G
    try:
        g = G.load()
        g(2065, 5563)
        return g
    except Exception as exc:          # no heightmap in this checkout
        pytest.skip("no canonical heightmap: %s" % exc)


def test_the_seat_is_recomputed_from_the_farms_plan():
    g = _ground()
    doc = _doc()
    assert P.seat_problems(doc, g) == []
    doc["sites"][0]["expected_at"] = [2065, 135, 5564]
    assert any("expected_at" in p for p in P.seat_problems(doc, g))
    doc = _doc()
    doc["sites"][0]["at_local"] = [-4, -12]          # inside Hollin's stall, by its keeper
    assert P.seat_problems(doc, g)
