"""tools/produce_buyer.py, the generator's own tests (data/produce_buyer.json; ECONOMY_V2 unit B2, the Trading Post).

The independent audit is unit B4's (tools/economy_audit.py); these hold the generator to its own rules, and every
price here is recomputed from the declared rate and the bank's tier hour WITHOUT calling the generator's own price
function, so a changed rounding or count inside tools/produce_buyer.py fails here."""
import copy
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bank as B  # noqa: E402
import produce_buyer as P  # noqa: E402

WAGE = {"early": 620, "deep": 1350, "nether": 2120}      # data/bank.json effort_model.tiers, MEASURED by bank.tier_hours
SPINE = {"stone_earth": 12, "nether_bulk": 9, "logs": 50, "crops": 20, "farm_misc": 20, "apricorns": 16, "berries": 33,
         "fish": 165, "meat": 165, "ranch": 165, "nether_wart": 20, "relic_coins": 20}


def _doc():
    return copy.deepcopy(P.load())


def _bank():
    return B.prices(B.load())


def _static(doc, bank=None, pts=(), **kw):
    return P.static_problems(doc, _bank() if bank is None else bank, list(pts), **kw)


def _files(doc=None):
    doc = doc or _doc()
    return doc, P.build(doc)


def _cmds(files, rel):
    return [ln for ln in files[P.fn_path(rel)] if not ln.startswith("#")]


# ------------------------------------------------------------------------------------------------ the spine
def test_the_banks_tier_hours_are_the_designs_wages():
    # what breaks without it: the table below is the design's ECONOMY_V2 1.1 numbers; if the bank's rates move, every
    # crate price moves with them, and this names why
    assert P.wages() == WAGE


def test_every_crate_is_its_count_times_the_tier_hour_over_its_rate():
    # what breaks without it: a rounding or count change inside the generator moves a price nobody re-derives
    doc = _doc()
    got = {}
    for c in doc["crates"]:
        if c.get("kp"):
            continue    # the kitchen/pharmacy goods: their price is the crafts rule's, pinned in the kp tests below
        raw = c["count"] * WAGE[c["tier"]] / c["rate_per_hour"]
        got[c["id"]] = int(math.floor(raw + 0.5))
    assert got == SPINE
    assert {k: v for k, v in P.prices(doc).items() if not k.startswith("kp_")} == SPINE


def test_the_emitted_functions_pay_the_spine_price_not_the_generators_say_so():
    doc, files = _files()
    for c in doc["crates"]:
        want = int(math.floor(c["count"] * WAGE[c["tier"]] / c["rate_per_hour"] + 0.5))
        sell = _cmds(files, "sell/%s" % c["id"])
        assert "scoreboard players set #price cob_pb %d" % want in sell, c["id"]
        sa = _cmds(files, "sellall/%s" % c["id"])
        assert "scoreboard players set #price cob_pb %d" % want in sa, c["id"]
        assert "scoreboard players set #n cob_pb %d" % c["count"] in sa, c["id"]


def test_a_mutated_generator_is_caught_by_the_independent_price_test(monkeypatch):
    # what breaks without it: this is the mutation that proves the test above is independent of the generator: change
    # the code, leave the data alone
    monkeypatch.setattr(P, "crate_price", lambda c, w: int(c["count"] * w[c["tier"]] / c["rate_per_hour"]) + 1)
    doc = _doc()
    assert P.prices(doc) != SPINE


def test_a_crate_that_rounds_to_nothing_is_refused():
    doc = _doc()
    doc["crates"][0]["rate_per_hour"] = 10 ** 9
    assert any("rounds to $0" in p for p in _static(doc))


def test_the_committed_data_and_output_pass():
    doc, files = _files()
    probs = _static(doc)
    assert probs == [], probs
    assert P.output_problems(doc, files) == []
    assert P.counter_problems(doc) == []


# ------------------------------------------------------------------------------------------------ E3: no allowance
def test_there_is_no_allowance_in_the_data_or_the_pack():
    # what breaks without it: E3 (the owner, 2026-10-13) is "no cap, no allowance"; a leftover leg, sold or cap score
    # would silently cap a player again
    doc, files = _files()
    assert "schedule" not in doc and "superseded_schedule" in doc
    assert P.fn_path("leg") not in files
    for rel, body in files.items():
        if rel.endswith(".mcfunction"):
            text = "\n".join(ln for ln in body if not ln.startswith("#"))
            assert not re.search(r"cob_pb_leg|cob_pb_sold|#cap\b|#badges|advancements=", text), rel
    assert set(doc["runtime"]["scores"].values()) == {"cob_pb", "cob_pb_cd", "cob_pb_owed"}


def test_a_function_that_names_the_old_allowance_is_refused():
    doc, files = _files()
    rel = P.fn_path("sell/crops")
    files[rel] = files[rel] + ["execute if score @s cob_pb_sold >= #cap cob_pb run return 0"]
    assert any("retired allowance" in p for p in P.output_problems(doc, files))


def test_a_data_file_that_brings_the_schedule_back_is_refused():
    doc = _doc()
    doc["schedule"] = {"rows": []}
    assert any("removed the allowance" in p for p in _static(doc))


# ------------------------------------------------------------------------------------------------ no round trip
def test_a_seller_at_or_under_the_crates_unit_is_refused():
    doc = _doc()
    probs = _static(doc, pts=[("a stall", "minecraft:cod", 10.3125)])   # fish: $165 / 16 = $10.3125 a unit
    assert any("sells minecraft:cod at $10.3125" in p for p in probs), probs
    assert _static(doc, pts=[("a stall", "minecraft:cod", 10.32)]) == []


def test_a_seller_at_or_under_a_specimens_price_is_refused():
    doc = _doc()
    probs = _static(doc, pts=[("a counter", "cobblemon:dragon_scale", 7)])
    assert any("sells it at $7" in p for p in probs), probs
    assert _static(doc, pts=[("a counter", "cobblemon:dragon_scale", 8)]) == []


def test_a_crate_item_the_bank_buys_is_refused():
    doc = _doc()
    probs = _static(doc, bank={"minecraft:melon_slice": 5})
    assert any("the bank buys minecraft:melon_slice" in p for p in probs), probs


def test_an_item_in_two_crates_is_refused():
    doc = _doc()
    doc["crates"][3]["items"] = doc["crates"][3]["items"] + ["minecraft:cobblestone"]
    assert any("minecraft:cobblestone is also in crate" in p for p in _static(doc))


# ------------------------------------------------------------------------------------------------ never sold
def test_a_never_sold_item_is_refused_in_a_crate_and_as_a_specimen():
    doc = _doc()
    doc["crates"][0]["items"].append("cobblemon:fire_stone")
    assert any("fire_stone is in never_sold" in p for p in _static(doc))
    doc = _doc()
    doc["crates"][0]["items"].append("minecraft:iron_block")
    assert any("matches never_sold" in p for p in _static(doc))
    doc = _doc()
    doc["specimens"]["items"].append("cobblemon:leftovers")
    probs = _static(doc)
    assert any("leftovers" in p and "never_sold" in p for p in probs), probs


def test_a_spawn_condition_block_is_refused_unless_the_crate_is_a_renewable_harvest():
    # what breaks without it: ECONOMY_V2 2.3, "paying strips encounters out of the world". Sand is a spawn block that
    # is DUG OUT; wheat is one that regrows (the crate's own spawn_block_ok says so)
    doc = _doc()
    doc["crates"][0]["items"].append("minecraft:sand")
    assert any("minecraft:sand is a spawn-condition block" in p for p in _static(doc))
    doc = _doc()
    crops = next(c for c in doc["crates"] if c["id"] == "crops")
    del crops["spawn_block_ok"]
    assert any("minecraft:wheat is a spawn-condition block" in p for p in _static(doc))


def test_an_unreachable_item_is_refused():
    doc = _doc()
    doc["crates"][0]["items"].append("minecraft:elytra")
    assert any("elytra" in p for p in _static(doc))


# ------------------------------------------------------------------------------------------------ specimens
def _notes():
    return P.notes_of(_doc())


def test_a_specimens_price_is_the_early_hour_over_sixty_kos_times_its_best_chance():
    # what breaks without it: ECONOMY_V2 2.2's formula, recomputed here from the notes without best_drop()
    doc, notes = _doc(), _notes()
    sp = P.specimen_prices(doc)
    for item in ("cobblemon:dragon_scale", "cobblemon:absorb_bulb", "cobblemon:razor_fang"):
        live = [d[2] for d in notes["items"][item]["droppers"] if d[4]]
        raw = 620 / (60 * max(live))
        assert sp[item] == max(1, min(200, int(math.floor(raw + 0.5)))), item
    assert sp["cobblemon:metal_powder"] == 200            # capped at 2 P (a 5% drop would be $207)
    assert sp["cobblemon:dragon_scale"] == 7
    assert min(sp.values()) >= 1 and max(sp.values()) <= 200


def test_a_crafted_item_is_not_a_specimen():
    doc = _doc()
    doc["specimens"]["items"].append("cobblemon:metal_coat")           # a recipe makes it
    assert any("recipe(s) make it" in p for p in _static(doc))


def test_a_prize_the_pack_hands_out_is_not_a_specimen():
    doc = _doc()
    doc["specimens"]["items"].append("cobblemon:big_root")
    del doc["specimens"]["excluded"]["cobblemon:big_root"]
    probs = _static(doc)
    assert any("big_root" in p and "never sold" in p for p in probs), probs


def test_a_stale_granted_exclusion_is_refused():
    doc = _doc()
    probs = _static(doc, grants={"data/rewards.json": ""})
    assert any("stale exclusion" in p for p in probs)


def test_a_new_drop_only_candidate_must_be_decided():
    doc = _doc()
    doc["specimens"]["items"].remove("cobblemon:sticky_barb")
    assert any("specimen candidate cobblemon:sticky_barb" in p for p in _static(doc))


def test_a_specimen_with_no_live_dropper_is_refused():
    doc = _doc()
    doc["specimens"]["items"].append("cobblemon:upgrade")
    assert any("upgrade" in p for p in _static(doc))


# ------------------------------------------------------------------------------------------------ the sales
def test_every_crate_counts_takes_pays_and_verifies_in_that_order():
    doc, files = _files()
    rel = P.fn_path("sell/crops")
    body = files[rel]
    i_take = next(i for i, ln in enumerate(body) if ln.endswith("clear @s #cobblers:produce_buyer/crops 32"))
    i_pay = next(i for i, ln in enumerate(body) if ln.startswith("function cobblers:produce_buyer/pay"))
    swapped = list(body)
    swapped[i_take], swapped[i_pay] = swapped[i_pay], swapped[i_take]
    files[rel] = swapped
    assert any(p.startswith("crate crops: the sale is not cooldown < count") for p in P.output_problems(doc, files))
    files = P.build(doc)
    files[rel] = [ln for ln in body if "#after" not in ln]
    assert any(p.startswith("crate crops") for p in P.output_problems(doc, files))
    files = P.build(doc)
    files[rel] = body + ["cobbledollars give @s 40"]
    assert any("outside the pay macro" in p for p in P.output_problems(doc, files))


def test_a_return_between_the_take_and_the_pay_is_refused():
    # what breaks without it: a return there leaves the goods taken and unpaid
    doc, files = _files()
    rel = P.fn_path("sell/fish")
    body = list(files[rel])
    i = next(i for i, ln in enumerate(body) if ln.startswith("execute unless score #took"))
    body.insert(i + 1, "execute if score @s cob_pb_owed matches 1.. run return 0")
    files[rel] = body
    assert any("a return between the take and the pay" in p for p in P.output_problems(doc, files))


def test_a_crate_pays_once_and_only_through_the_macro():
    doc, files = _files()
    assert _cmds(files, "pay") == ["$cobbledollars give @s $(amount)"]
    for c in doc["crates"]:
        cmds = _cmds(files, "sell/%s" % c["id"])
        assert sum(1 for ln in cmds if ln.startswith("function cobblers:produce_buyer/pay")) == 1
        assert not any("cobbledollars remove" in ln or "cobbledollars give" in ln for ln in cmds)


def test_the_bounded_take_is_one_macro_line_per_crate():
    doc, files = _files()
    for c in doc["crates"]:
        pred = P.predicate(c)
        assert _cmds(files, "take/%s" % c["id"]) == ["$execute store result score #took cob_pb run clear @s %s $(n)" % pred]
        sa = _cmds(files, "sellall/%s" % c["id"])
        assert "function cobblers:produce_buyer/take/%s with storage cobblers:produce_buyer take" % c["id"] in sa
        # whole crates only: the count is divided by the crate size before anything is taken
        assert "scoreboard players operation #crates cob_pb /= #n cob_pb" in sa
        assert "execute if score #crates cob_pb matches ..0 run return 0" in sa


def test_sell_all_takes_every_category_then_the_specimens_then_pays_once():
    doc, files = _files()
    cmds = _cmds(files, "sell/all")
    calls = [ln.split()[1] for ln in cmds if ln.startswith("function cobblers:produce_buyer/sellall/")]
    assert calls == ["cobblers:produce_buyer/sellall/%s" % c["id"] for c in doc["crates"]] + \
        ["cobblers:produce_buyer/sellall/specimens"]
    assert sum(1 for ln in cmds if ln == "function cobblers:produce_buyer/pay with storage cobblers:produce_buyer pay") == 1
    first = next(i for i, ln in enumerate(cmds) if ln.startswith("function cobblers:produce_buyer/sellall/"))
    pay = next(i for i, ln in enumerate(cmds) if ln.startswith("function cobblers:produce_buyer/pay"))
    # the one return between the first take and the pay is the "nothing taken" gate
    between = [ln for ln in cmds[first:pay] if "return" in ln]
    assert len(between) == 1 and between[0].startswith("execute if score #total cob_pb matches ..0 run return run tellraw")
    for rel in [r for r in files if "/sellall/" in r and r.endswith(".mcfunction")]:
        assert not any("cobbledollars" in ln for ln in files[rel] if not ln.startswith("#")), rel


def test_sell_all_with_a_return_between_the_takes_and_the_pay_is_refused():
    doc, files = _files()
    rel = P.fn_path("sell/all")
    body = list(files[rel])
    i = next(i for i, ln in enumerate(body) if ln.startswith("function cobblers:produce_buyer/sellall/specimens"))
    body.insert(i, "execute if score #short cob_pb matches 1 run return 0")
    files[rel] = body
    assert any("sell/all: a return between the first take" in p for p in P.output_problems(doc, files))


def test_sell_all_missing_a_category_is_refused():
    doc, files = _files()
    rel = P.fn_path("sell/all")
    files[rel] = [ln for ln in files[rel] if not ln.endswith("sellall/ranch")]
    assert any("sell/all calls" in p for p in P.output_problems(doc, files))


def test_the_specimens_function_clears_each_piece_and_credits_pieces_times_price():
    doc, files = _files()
    sp = P.specimen_prices(doc)
    cmds = _cmds(files, "sellall/specimens")
    for item, price in sp.items():
        i = cmds.index("execute store result score #took cob_pb run clear @s %s" % item)
        assert cmds[i - 2] == "scoreboard players set #price cob_pb %d" % price
        assert "scoreboard players operation #part cob_pb *= #price cob_pb" in cmds[i:i + 4]
    assert not any("return" in ln or "cobbledollars" in ln for ln in cmds)


def test_a_short_take_records_the_taken_share_as_owed_and_pays_nothing():
    doc, files = _files()
    st = _cmds(files, "short_take")
    assert st[-1] == "return 1" and [ln for ln in st if "return" in ln] == ["return 1"]
    assert any(ln.startswith("scoreboard players operation @s cob_pb_owed += ") for ln in st)
    assert not any("cobbledollars" in ln for ln in st)


# ------------------------------------------------------------------------------------------------ the dialogue
def test_the_pack_ships_its_tags_and_one_option_per_crate_with_its_price():
    doc, files = _files()
    cp = P.prices(doc)
    assert files["data/cobblers/tags/item/produce_buyer/crops.json"]["values"] == \
        next(c for c in doc["crates"] if c["id"] == "crops")["items"]
    # a crate that names the jar's tag ships no tag of its own
    assert "data/cobblers/tags/item/produce_buyer/logs.json" not in files
    dlg = json.dumps(files["data/cobblers/dialogues/dlg_produce_buyer_hollin_farm.json"])
    assert "function cobblers:produce_buyer/sell/all" in dlg
    for c in doc["crates"]:
        if c.get("menu") is False:
            # a kitchen/pharmacy good has a sale function but no button: it sells through "sell everything I can"
            assert "function cobblers:produce_buyer/sell/%s" % c["id"] not in dlg
            assert P.fn_path("sell/%s" % c["id"]) in files
            continue
        assert "function cobblers:produce_buyer/sell/%s" % c["id"] in dlg
        assert "A crate of %d %s ($%d)" % (c["count"], c["label"], cp[c["id"]]) in dlg
    assert "cobblers:produce_buyer/pay" in "\n".join(files[P.fn_path("sell/fish")])


def test_every_function_is_within_the_servers_limits():
    import function_limits
    doc, files = _files()
    for rel, body in files.items():
        if rel.endswith(".mcfunction"):
            assert function_limits.check_lines(body, rel) == [], rel


# ------------------------------------------------------------------------------------------------ the sites
def test_every_sited_counter_has_a_trading_post_and_a_missing_one_is_named():
    doc = _doc()
    assert P.counter_problems(doc) == []
    markets = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    sited = {c["id"] for c in markets["counters"] if c.get("status") == "sited"}
    have = {s["counter"] for s in doc["sites"] if s.get("counter")}
    assert sited <= have
    doc["sites"] = [s for s in doc["sites"] if s.get("counter") != "pacifidlog"]
    assert any("counter pacifidlog" in p for p in P.counter_problems(doc))


def test_an_unsited_site_has_a_reason_and_is_not_built_or_placed():
    # what breaks without it: an NPC class and a dialogue for a seat nobody verified, placed by R18PB over RCON
    doc, files = _files()
    unsited = [s for s in doc["sites"] if s.get("status") == "unsited"]
    # Fossick and Northlight were the last two (squares authored and posts seated 2026-10-14); none is unsited now, so the
    # property is exercised on a synthetic one: any site marked unsited, with its reason, is not built or placed
    assert {s["id"] for s in unsited} == set()
    synthetic = next(s for s in doc["sites"] if s["id"] == "tp_pallet")
    synthetic.update(status="unsited", unsited_why="a synthetic reason")
    files = P.build(doc)
    unsited = [synthetic]
    for s in unsited:
        assert s["unsited_why"]
        assert "data/cobblers/dialogues/dlg_produce_buyer_%s.json" % s["id"] not in files
        assert s not in P.sited(doc)


class _FakeTown:
    rect = (0, 0, 20, 20)

    def __init__(self, blocked=None):
        self._blocked = blocked or {}

    def blocked(self, x, z):
        return self._blocked.get((x, z))

    def floor_at(self, x, z):
        return 64


def _model(**kw):
    return {"town": _FakeTown(kw.get("blocked")), "occupied": kw.get("occupied", set()),
            "points": kw.get("points", []), "signposts": False}


def test_a_cell_the_squares_builder_blocks_is_refused(monkeypatch):
    monkeypatch.setattr(P, "route_points", lambda: [])
    assert any("blocked on the square: street" in p for p in P.cell_problems(_model(blocked={(5, 5): "street"}), 5, 5))
    assert P.cell_problems(_model(), 5, 5) == []


def test_a_cell_beside_a_piece_or_an_npc_is_refused(monkeypatch):
    monkeypatch.setattr(P, "route_points", lambda: [])
    assert any("within" in p for p in P.cell_problems(_model(occupied={(6, 5)}), 5, 5))
    assert any("blocks from an NPC" in p for p in P.cell_problems(_model(points=[(8, 5)]), 5, 5))       # 3.0 < 3.5
    assert not any("blocks from an NPC" in p for p in P.cell_problems(_model(points=[(9, 5)]), 5, 5))   # 4.0
    assert any("blocks from an NPC" in p for p in P.cell_problems(_model(), 5, 5, others=[(7, 6)]))


def test_a_cell_on_a_walked_route_is_refused(monkeypatch):
    monkeypatch.setattr(P, "route_points", lambda: [(5, 7)])
    assert any("walked route line" in p for p in P.cell_problems(_model(), 5, 5))
    monkeypatch.setattr(P, "route_points", lambda: [(5, 9)])
    assert not any("walked route line" in p for p in P.cell_problems(_model(), 5, 5))


def test_yaw_faces_the_target():
    assert P.yaw_toward(0, 0, 0, 10) == 0          # south
    assert P.yaw_toward(0, 0, -10, 0) == 90        # west
    assert P.yaw_toward(0, 0, 0, -10) == 180       # north
    assert P.yaw_toward(0, 0, 10, 0) == -90        # east


def _ground():
    import ground as G
    try:
        g = G.load()
        g(2065, 5563)
        return g
    except Exception as exc:          # no heightmap in this checkout
        pytest.skip("no canonical heightmap: %s" % exc)


def test_hollins_seat_is_recomputed_from_the_farms_plan():
    g = _ground()
    doc = _doc()
    hollin = [s for s in doc["sites"] if s["anchor"] == "apricorn_farm"]
    doc["sites"] = hollin
    assert P.seat_problems(doc, g) == []
    doc["sites"][0]["expected_at"] = [2065, 135, 5564]
    assert any("expected_at" in p for p in P.seat_problems(doc, g))
    doc = _doc()
    doc["sites"] = [dict(s, at_local=[-4, -12]) for s in doc["sites"] if s["anchor"] == "apricorn_farm"]   # inside the stall
    assert P.seat_problems(doc, g)


def test_the_town_squares_seats_hold_the_squares_builders_model():
    # needs derived/towns/<town>_plan.json (python tools/town_plan.py <town>) and the kits: skipped where absent
    doc = _doc()
    towns = {s["settlement"] for s in P.sited(doc) if s["anchor"] == "town_square"}
    missing = [t for t in sorted(towns) if t != "hometown" and not (ROOT / "derived" / "towns" / ("%s_plan.json" % t)).is_file()]
    if missing:
        pytest.skip("no derived town plan for %s" % missing)
    g = _ground()
    probs = P.seat_problems(doc, g)
    assert probs == [], probs
