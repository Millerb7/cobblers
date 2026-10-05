"""The town squares' stall keepers and the closed spend-money gaps (tools/markets.py `stalls`, data/markets.json);
since 2026-10-06 the counters' merchants too (decision counters_are_merchants: every seller is a merchant).

The builder's own tests (the independent audit of the stalls is a separate unit). They cover:
  - the squares' contract (data/plaza_centres.json, another builder's): read from a fixture, since the real file may
    not exist yet; a contract seat wins over the record's fallback, an empty contract stall is refused
  - the committed data: every static rule, the curve, the built purchases and menus
  - the static rules biting on record mutations (spawn blocks, backpack items, gated provisions, unverified ids)
  - the purchase generator mutated, data untouched: every stall purchase is named
  - the site rules that need no derived/: the deck rule (Pacifidlog), the donor footprints (Pallet), the earthwork replay
  - R17M places the stall keepers
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import markets as M  # noqa: E402
import markets_audit as MA  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "plaza_centres.json"


def _doc():
    return json.loads(json.dumps(M.load()))


def _towns():
    return json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]


def _stall(doc, sid):
    return next(s for s in doc["stalls"] if s["id"] == sid)


def _static(doc, plazas=None):
    import progression_pack as PP
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    planned = {f["id"] for f in PP.plan(prog, placements=pl)["flags"]}
    traders = {t["id"]: t for t in json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))["traders"]}
    return (M.static_problems(doc, planned, _towns(), traders) + M.stall_problems(doc, _towns(), plazas or {})
            + M.collision_problems(doc))


# ------------------------------------------------------------------------------------------------ the contract
def test_the_contract_is_read_with_its_towns():
    p = M.load_plazas(FIXTURE)
    assert sorted(p) == ["gym1_town_stall_1", "gym1_town_stall_2", "gym1_town_stall_3", "tableland_stop_stall_1"]
    assert {s["_town"] for s in p.values()} == {"gym1_town", "tableland_stop"}
    assert M.load_plazas(ROOT / "tests" / "fixtures" / "no_such_file.json") == {}


def test_a_contract_seat_wins_and_the_rest_fall_back():
    doc, p = M.load(), M.load_plazas(FIXTURE)
    # since 2026-10-06 (decision counters_are_merchants) a counter's keeper is a merchant too, seated by the same rule
    assert M.npc_placements(doc, p) == []
    merch = {m["stall"]: m for m in M.stall_merchants(doc, p)}
    keep = {m["stall"]: m for m in merch.values() if m["kind"] == "counter"}
    assert keep["stoneford"]["at"] == (1745, 139, 3622) and keep["stoneford"]["yaw"] == 180
    # the fixture's stall 2 is staffed by whichever record names it (2026-10-03: the terrace seedsman; the masons' yard
    # moved to stall 6, which the fixture does not have, so it falls back); since 2026-10-04 a stall's keeper is a
    # merchant, seated by the same rule
    assert merch["stoneford_terrace_seedsman"]["at"] == (1755, 139, 3632)
    assert merch["stoneford_masons_yard"]["at"] == tuple(_stall(doc, "stoneford_masons_yard")["at"])
    assert keep["redbrow"]["at"] == (4838, 162, 5690)
    # not in the contract: the record's own fallback site
    assert keep["viltri_quay"]["at"] == tuple(next(c for c in doc["counters"] if c["id"] == "viltri_quay")["at"])
    assert merch["fenhide_trapper"]["at"] == tuple(_stall(doc, "fenhide_trapper")["at"])
    assert merch["fenhide_trapper"]["yaw"] == _stall(doc, "fenhide_trapper")["yaw"]
    assert M.stall_placements(doc, p) == []
    # the independent audit reads the same contract by its own route
    assert MA.contract_seats(FIXTURE)["gym1_town_stall_1"] == [1745, 139, 3622, 180]


def test_the_fixture_contract_is_fully_staffed_and_its_themes_reported():
    doc, p = M.load(), M.load_plazas(FIXTURE)
    assert M.stall_problems(doc, _towns(), p) == []
    rep = M.contract_report(doc, p)
    assert any("stoneford_herbalist" in r and "'fish'" in r for r in rep)
    assert any("viltri_boatwright: stall gym2_town_stall_4 is not seated" in r for r in rep)


def test_the_real_contract_is_fully_staffed_with_matching_themes():
    """data/plaza_centres.json (the squares' builder's, merged 2026-10-03): every stall staffed once, and every record
    that names a contract stall carries that stall's theme word."""
    doc, p = M.load(), M.load_plazas()
    if not p:
        pytest.skip("data/plaza_centres.json is absent")
    assert M.stall_problems(doc, _towns(), p) == []
    assert [r for r in M.contract_report(doc, p) if "the contract's stall" in r] == []


def test_a_contract_keeper_on_the_deck_faces_its_stall():
    pl = _placements()
    plan = pl["settlements"]["sea_town"]["plan"]
    # sea_town_stall_1: the stall at (5154, 7383), its keeper behind it at (5153, 7383) facing east (yaw -90)
    ok = M.deck_problems("k", 5153, 63, 7383, -90, "sea_town", plan, pl, _world(), face=(5154, 7383))
    assert not [e for e in ok if "faces yaw" in e], ok
    away = M.deck_problems("k", 5153, 63, 7383, 90, "sea_town", plan, pl, _world(), face=(5154, 7383))
    assert any("but its stall at [5154, 7383] is at yaw -90" in e for e in away), away


def test_an_empty_contract_stall_and_a_far_keeper_are_refused(tmp_path):
    c = json.loads(FIXTURE.read_text(encoding="utf-8"))
    c["towns"]["gym1_town"]["stalls"].append(
        {"id": "gym1_town_stall_9", "at": [1740, 139, 3610], "keeper_at": [1740, 139, 3620, 0], "sells": "nothing"})
    f = tmp_path / "plaza_centres.json"
    f.write_text(json.dumps(c), encoding="utf-8")
    probs = M.stall_problems(M.load(), _towns(), M.load_plazas(f))
    assert any("gym1_town_stall_9 is staffed by 0" in x for x in probs)
    assert any("gym1_town_stall_9's keeper_at is 10.0 blocks" in x for x in probs)


def test_one_stall_two_keepers_is_refused():
    doc = _doc()
    _stall(doc, "stoneford_bakehouse")["stall"] = "gym1_town_stall_2"
    assert any("gym1_town_stall_2 is staffed by" in x for x in M.stall_problems(doc, _towns(), {}))


# ------------------------------------------------------------------------------------------------ the committed data
def test_the_committed_markets_and_stalls_pass_every_offline_rule():
    doc = M.load()
    assert _static(doc) == []
    assert M.curve_problems(doc) == []
    files, npcs = M.build(doc, {})
    assert M.output_problems(doc, files) == []
    assert M.output_problems(doc, files, {}) == []          # with the seats: every summon on its seat, turned to its yaw
    assert npcs == []                                       # no dialogue keeper since 2026-10-06
    assert not [k for k in files if "/dialogues/" in k or "/npcs/" in k]
    summons = [x for body in files.values() if isinstance(body, list) for x in body if x.startswith("summon ")]
    # one summon per stall or counter record that names where its keeper stands -- counted from data/markets.json
    # itself, not pasted (it was a literal 33 until Arrow Creeks Farm's stand made 34 on 2026-10-05); an unsited stall
    # has no `at`; every sited counter has one (2026-10-06: the counters are merchants)
    raw = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    standing = [s["id"] for s in raw["stalls"] if isinstance(s.get("at"), list) and len(s["at"]) == 3]
    assert not [s["id"] for s in raw["stalls"] if s.get("status") == "unsited" and s.get("at")]
    counters = [c["id"] for c in raw["counters"] if c.get("status") == "sited"]
    assert len(summons) == len(M.emitted_stalls(doc)) + len(M.emitted(doc)) == len(standing) + len(counters) > 0


def test_every_town_with_a_square_or_a_clerk_now_has_a_keeper_or_says_why():
    doc = M.load()
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]
    traders = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))["traders"]
    built = {c["town"] for c in M.emitted(doc)} | {s["town"] for s in M.emitted_stalls(doc)}
    excused = {n["town"] for n in doc["no_counter"]}
    want = {t for t, v in pl.items() if ((v.get("plan") or {}).get("plaza"))} | {t["settlement"] for t in traders}
    assert sorted(want - built - excused) == []
    # the survey's gaps, by name
    for t in ("hometown", "sunset_west", "sea_town", "tableland_stop"):
        assert t in built, t
    assert len([s for s in M.emitted_stalls(doc) if s["town"] == "tea_town"]) >= 1


def test_the_curve_is_unchanged_by_provisions_and_counts_a_gated_stall_line():
    doc = _doc()
    before = {b: ask for b, ask, _s, _i, _r in M.curve(doc)}
    want = {1: 6550, 2: 11450, 3: 20000, 4: 29800, 5: 41300, 6: 54800, 7: 71000, 8: 99500}
    assert before == want      # the survey's figures (TOWN_SQUARES_SURVEY 5): the stalls added nothing to the curve
    _stall(doc, "stoneford_masons_yard")["stock"].append(
        {"id": "x", "item": "minecraft:anvil", "name": "Anvil", "count": 1, "price": 777, "gate": "gym1_cleared",
         "strand": "convenience", "why": "probe", "verified": "probe"})
    after = {b: ask for b, ask, _s, _i, _r in M.curve(doc)}
    assert all(after[b] == before[b] + 777 for b in range(1, 9))


def test_places_beyond_towns_are_held_to_coverage():
    doc = _doc()
    doc["no_counter"] = [n for n in doc["no_counter"] if n["town"] != "deep_city"]
    assert any("town deep_city: 0 entries" in x for x in _static(doc))
    doc = _doc()
    doc["places_beyond_towns"][0]["source"] = "data/no_such_city.json"
    assert any("does not exist" in x for x in _static(doc))


# ------------------------------------------------------------------------------------------------ the rules bite
@pytest.mark.parametrize("item, needle", [
    ("minecraft:cake", "spawn condition"),
    ("minecraft:wheat_seeds", "it places minecraft:wheat"),
    ("sophisticatedbackpacks:feeding_upgrade", "the ladder is the counters'"),
    ("cobblemon:great_ball", "is not a provision"),
    ("minecraft:diamond_sword", "is not a provision"),
])
def test_a_stall_line_that_is_not_a_provision_is_refused(item, needle):
    doc = _doc()
    _stall(doc, "fossick_pit_tools")["stock"][0]["item"] = item
    assert any(needle in x for x in M.stall_problems(doc, _towns(), {})), item


def test_a_gated_provision_an_unverified_id_and_a_money_printer_are_refused():
    doc = _doc()
    s = _stall(doc, "stoneford_bakehouse")
    s["stock"][0]["gate"] = "gym1_cleared"
    s["stock"][1].pop("verified")
    s["stock"][2]["price"] = 2          # two pumpkin pies for $2: bank.json buys one back for 20
    s["unverified"] = [{"item": "minecraft:bread", "why": "probe"}]
    probs = M.stall_problems(doc, _towns(), {})
    assert any("a provision is ungated" in x for x in probs)
    assert any("no `verified`" in x for x in probs)
    assert any("not above the bank's sell-back" in x for x in probs)
    assert any("listed unverified and stocked" in x for x in probs)


def test_a_counter_with_neither_clerk_nor_stall_cannot_be_sited():
    doc = _doc()
    c = next(c for c in doc["counters"] if c["id"] == "redbrow")
    assert c["near_trader"] is None and c["status"] == "sited"
    assert not [x for x in _static(doc) if "redbrow" in x]
    c["stall"] = None
    assert any("redbrow: sited with no near_trader to stand beside and no stall" in x for x in _static(doc))


def test_a_counter_line_gated_or_missing_its_dropped_gate_is_refused():
    """2026-10-06 (decision counters_are_merchants): a counter's merchant shows every line to every player, so a line
    may not carry a gate; on a critical-path counter every line records its own badge in gate_dropped (the old rule's
    gate, kept as a record); a counter needs a category and a price that divides by its count."""
    def counter(doc, cid):
        return next(c for c in doc["counters"] if c["id"] == cid)
    doc = _doc()
    assert not [x for x in _static(doc) if "gate" in x]
    st = counter(doc, "stoneford")
    st["stock"][0]["gate"] = "gym1_cleared"                         # re-gated
    st["stock"][1].pop("gate_dropped")                              # its record lost
    st["stock"][2]["gate_dropped"] = dict(st["stock"][2]["gate_dropped"], gate="gym2_cleared")   # another town's badge
    st["stock"][3]["gate_dropped"] = dict(st["stock"][3]["gate_dropped"], decision="nobody_decided")
    st["stock"][4]["gate_dropped"] = dict(st["stock"][4]["gate_dropped"], why="")
    hw = counter(doc, "highwire")
    hw["stock"][3]["price"] = 1751                                  # five Great Balls: does not divide
    hw["category"] = 'Relay "Stores"'
    counter(doc, "pallet")["stock"][0]["gate_dropped"] = {"gate": "gym1_cleared", "decision": "counters_are_merchants",
                                                          "why": "probe"}
    probs = _static(doc)
    assert any("stoneford item copper_backpack: gated on 'gym1_cleared'" in p for p in probs), probs
    assert any("stoneford item stonecutter_upgrade: a critical-path counter at badge 1 records a dropped gate None" in p
               for p in probs)
    assert any("stoneford item anvil_upgrade: a critical-path counter at badge 1 records a dropped gate 'gym2_cleared'"
               in p for p in probs)
    assert any("stoneford item hard_stone: gate_dropped" in p for p in probs)
    assert any("stoneford item crafting_upgrade: gate_dropped" in p for p in probs)
    assert any("highwire item great_ball: $1751 for 5 does not divide" in p for p in probs)
    assert any("counter highwire: category" in p for p in probs)
    assert any("pallet item backpack: Pallet's shelf was never gated" in p for p in probs)
    # and the decision the records cite must exist
    doc = _doc()
    doc["decisions"] = []
    assert sum("gate_dropped" in p for p in _static(doc)) == sum(
        1 for c in doc["counters"] for it in c["stock"] if it.get("gate_dropped"))


# ------------------------------------------------------------------------------------------------ generator mutation
def _merchant_named(doc, files, needle, plazas=None):
    return {p.split(" merchant:")[0] for p in M.output_problems(doc, files, plazas) if needle in p}


def _every_stall(doc):
    """Every merchant the pack summons: each sited stall's and, since 2026-10-06, each sited counter's."""
    return {"%s %s" % (kind, s["id"]) for s, kind in M.merchant_records(doc)}


def test_a_mutated_shop_generator_is_caught_at_every_stall(monkeypatch):
    # the generator, not the data: drop each shop's last offer, then double every price
    real = M.merchant_shop
    monkeypatch.setattr(M, "merchant_shop", lambda s: [dict(real(s)[0], Offers=real(s)[0]["Offers"][:-1])])
    doc = M.load()
    files, _ = M.build(doc, {})
    assert _merchant_named(doc, files, ": offers ") == _every_stall(doc)

    def dear(s):
        cat = real(s)[0]
        return [dict(cat, Offers=[dict(o, Price=str(int(o["Price"]) * 2)) for o in cat["Offers"]])]
    monkeypatch.setattr(M, "merchant_shop", dear)
    files, _ = M.build(doc, {})
    assert _merchant_named(doc, files, "each, but the line is") == _every_stall(doc)


def test_a_mutated_summon_is_caught_at_every_stall(monkeypatch):
    import traders as TR
    real = TR.summon_line
    monkeypatch.setattr(TR, "summon_line", lambda kind, x, y, z, data: real(
        kind, x + 1, y, z, {k: v for k, v in data.items() if k not in ("NoAI", "Rotation")}))
    doc = M.load()
    files, _ = M.build(doc, {})
    assert _merchant_named(doc, files, "no NoAI:1b") == _every_stall(doc)
    assert _merchant_named(doc, files, "summoned at", {}) == _every_stall(doc)
    assert _merchant_named(doc, files, "rotation None", {}) == _every_stall(doc)


def test_a_dialogue_keeper_removal_dropped_or_moved_after_the_summons_is_caught(monkeypatch):
    """2026-10-06 ("need the steve traders gone"): each town's _place runs _clear, which kills every cobblemon:npc on
    a merchant seat, before any summon. The generator mutated three ways, data untouched."""
    real = M.merchant_functions
    doc = M.load()

    def no_call(doc, plazas):         # _place stops calling _clear
        return {k: [x for x in v if not x.endswith("_clear")] for k, v in real(doc, plazas).items()}
    monkeypatch.setattr(M, "merchant_functions", no_call)
    files, _ = M.build(doc, {})
    assert _merchant_named(doc, files, "does not run _clear before its summons") == _every_stall(doc)

    def no_kills(doc, plazas):        # _clear kills nothing
        return {k: [x for x in v if not (k.endswith("_clear.mcfunction") and x.startswith("kill "))]
                for k, v in real(doc, plazas).items()}
    monkeypatch.setattr(M, "merchant_functions", no_kills)
    files, _ = M.build(doc, {})
    assert _merchant_named(doc, files, "does not remove the dialogue keeper at its seat") == _every_stall(doc)

    def late(doc, plazas):            # the kills move into _done, after the summons (the 2026-10-04 shape)
        files = real(doc, plazas)
        for k in [k for k in files if k.endswith("_clear.mcfunction")]:
            done = k.replace("_clear.mcfunction", "_done.mcfunction")
            files[done] = files[done] + [x for x in files[k] if x.startswith("kill ")]
            files[k] = [x for x in files[k] if not x.startswith("kill ")]
        return files
    monkeypatch.setattr(M, "merchant_functions", late)
    files, _ = M.build(doc, {})
    assert _merchant_named(doc, files, "its town's _done kills a Cobblemon NPC") == _every_stall(doc)


def test_a_stall_dialogue_or_purchase_left_beside_a_merchant_is_caught():
    # the money path is the merchant's own screen: a purchase function or a menu left for a stall could charge twice
    doc = M.load()
    files, _ = M.build(doc, {})
    s = M.emitted_stalls(doc)[0]
    c = M.emitted(doc)[0]
    files["data/cobblers/function/stalls/%s/x.mcfunction" % s["id"]] = ["say x"]
    files["data/cobblers/dialogues/dlg_stall_%s.json" % s["id"]] = {}
    # and a counter's (2026-10-06): its old menu, class and purchase function
    files["data/cobblers/dialogues/dlg_market_%s.json" % c["id"]] = {}
    files["data/cobblers/npcs/npc_market_%s.json" % c["id"]] = {}
    files["data/cobblers/function/markets/%s/%s.mcfunction" % (c["id"], c["stock"][0]["id"])] = ["say x"]
    files["data/cobblers/function/stalls/merchants/extra.mcfunction"] = ["execute as @p run cobbledollars remove @s 5"]
    probs = M.output_problems(doc, files)
    assert sum("beside its merchant" in p for p in probs) == 4
    assert sum("a counter's purchase function or charge macro is emitted" in p for p in probs) == 1
    assert any("extra.mcfunction: a merchant function charges" in p for p in probs)
    assert M.output_problems(doc, M.build(doc, {})[0]) == []


def test_a_gated_stall_line_an_indivisible_price_and_a_missing_category_are_refused():
    doc = _doc()
    s = _stall(doc, "fossick_pit_tools")
    s["stock"][0]["gate"] = "gym1_cleared"
    s["stock"][0]["strand"] = "convenience"
    s["stock"][3]["price"] = 481          # 4 lanterns: does not divide
    s["category"] = ""
    probs = M.stall_problems(doc, _towns(), {})
    assert any("fossick_pit_tools item iron_pickaxe: gated on 'gym1_cleared'" in p for p in probs)
    assert any("fossick_pit_tools item lantern: $481 for 4 does not divide" in p for p in probs)
    assert any("fossick_pit_tools: category ''" in p for p in probs)
    doc = _doc()
    doc["stall_merchant"]["remove_radius"] = 4
    assert any("remove_radius 4" in p for p in M.stall_problems(doc, _towns(), {}))


def test_the_world_check_reads_every_merchant_back(monkeypatch):
    """verify() against a fake server: a right world passes; a missing merchant, a dialogue keeper left beside one, a
    merchant off its seat and a shop that differs are each named. The shop reply puts each item's id BEFORE its count,
    as the game may write it, so the read does not depend on the summon's key order."""
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    doc = M.load()
    ms = M.stall_merchants(doc)
    stalls = {s["id"]: s for s, _kind in M.merchant_records(doc)}      # the counters' merchants too, since 2026-10-06
    by_tag = {m["tag"]: m for m in ms}

    def world(missing=(), npc_left=(), off_seat=(), cheap=()):
        def rc(cmd):
            import re as _re
            if cmd.startswith(("forceload", "execute if loaded")):
                return "Test passed"
            tag = _re.search(r"tag=(cobblers_stall_[a-z0-9_]+)", cmd)
            m = by_tag.get(tag.group(1)) if tag else None
            if cmd.startswith("execute if entity @e[type=cobblemon:npc"):
                at = tuple(int(float(v)) for v in _re.search(r"x=([-0-9.]+),y=([-0-9.]+),z=([-0-9.]+)", cmd).groups())
                hit = [k for k in npc_left if by_tag["cobblers_stall_" + k]["at"] == at]
                return "Test passed, count: 1" if hit else "Test failed"
            if m is None or m["stall"] in missing:
                return "Test failed" if cmd.startswith("execute") else "No entity was found"
            if cmd.startswith("execute if entity") and "distance=..0.6" in cmd:
                return "Test failed" if m["stall"] in off_seat else "Test passed, count: 1"
            if cmd.startswith("execute if entity"):
                return "Test passed, count: 1"
            if cmd.startswith("data get entity"):
                offers = ", ".join('{Item: {id: "%s", count: 1}, Price: "%d"}' % (
                    it["item"], it["price"] // it["count"] - (1 if m["stall"] in cheap else 0))
                    for it in stalls[m["stall"]]["stock"])
                return "Villager has the following entity data: [{Category: \"x\", Offers: [%s]}]" % offers
            return ""
        return rc
    assert M.verify(world(), doc) == []
    got = M.verify(world(missing=["viltri_fishmonger"], npc_left=["sunset_net_loft"], off_seat=["tilpey_stationer"],
                         cheap=["fenhide_trapper"]), doc)
    assert any(p.startswith("viltri_fishmonger: 0 merchants") for p in got)
    assert any(p.startswith("sunset_net_loft: 1 Cobblemon NPC(s) still within") for p in got)
    assert any(p.startswith("tilpey_stationer: its merchant is not on its seat") for p in got)
    assert any(p.startswith("fenhide_trapper: its shop reads") for p in got)
    assert len(got) == 4
    # the counters' merchants are read back the same way: Steepside's Tea House Kitchen with its Steve still beside it
    got = M.verify(world(missing=["holdfast"], npc_left=["steepside"], cheap=["greenhollow"]), doc)
    assert any(p.startswith("holdfast: 0 merchants") for p in got)
    assert any(p.startswith("steepside: 1 Cobblemon NPC(s) still within") for p in got)
    assert any(p.startswith("greenhollow: its shop reads") for p in got)
    assert len(got) == 3


# ------------------------------------------------------------------------------------------------ sites without derived/
def _world():
    return json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))


def _placements():
    return json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))


def test_the_deck_rule_passes_the_raft_keepers_and_refuses_the_fence():
    pl = _placements()
    plan = pl["settlements"]["sea_town"]["plan"]
    doc = M.load()
    for rec in [c for c in doc["counters"] if c["town"] == "sea_town"] + [s for s in doc["stalls"] if s["town"] == "sea_town"]:
        x, y, z = rec["at"]
        assert M.deck_problems("k", x, y, z, rec["yaw"], "sea_town", plan, pl, _world()) == [], rec["id"]
    # on a corner post of the raft (a jungle fence under a lantern, measured from the earthwork 2026-10-03): named
    post = M.deck_problems("k", 5153, 63, 7387, M.plaza_yaw(plan, 5153, 7387), "sea_town", plan, pl, _world())
    assert any("minecraft:jungle_fence stands at (5153, 63, 7387)" in e for e in post), post
    # on the raft's west edge, x5152 (deck_ground's last cell there): its west neighbour is open water
    edge = M.deck_problems("k", 5152, 63, 7380, M.plaza_yaw(plan, 5152, 7380), "sea_town", plan, pl, _world())
    assert any("(5151, 7380) is not a deck cell" in e for e in edge), edge
    # one block up is not on the deck
    assert any("but the deck is y62" in e for e in M.deck_problems("k", 5166, 64, 7374, 45, "sea_town", plan, pl, _world()))


def test_the_earthwork_replay_applies_order_air_keep_and_replace():
    pl = {"placements": [{"settlement": "t", "kind": "earthwork", "commands": [
        "fill 0 0 0 4 0 4 minecraft:stone", "setblock 1 0 1 minecraft:air", "fill 0 0 0 4 0 4 minecraft:dirt replace minecraft:grass_block",
        "fill 2 0 2 2 0 2 minecraft:glass keep", "setblock 3 0 3 minecraft:oak_fence[east=true]", "# a comment"]}]}
    got = M.earthwork_blocks(pl, "t", [(0, 0, 0), (1, 0, 1), (2, 0, 2), (3, 0, 3), (9, 0, 9)])
    assert got == {(0, 0, 0): "minecraft:stone", (2, 0, 2): "minecraft:stone", (3, 0, 3): "minecraft:oak_fence[east=true]"}


def test_pallets_keeper_stands_outside_every_donor_building_on_its_ground():
    import ground as G
    c = next(c for c in M.load()["counters"] if c["id"] == "pallet")
    fps, unknown = M.donor_footprints("hometown", _placements())
    assert unknown == [] and fps["hometown_pokemart"] == (1467, 5239, 1489, 5260)
    x, y, z = c["at"]
    assert not [p for p, (a, b, cc, d) in fps.items() if a - 1 <= x <= cc + 1 and b - 1 <= z <= d + 1]
    assert y == int(round(G.Ground(None)(x, z))) + 1


# ------------------------------------------------------------------------------------------------ the apply step
def test_r17m_places_every_counter_keeper_and_every_stall_merchant_then_reads_them_back():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    i = src.index('out.append(("R17M", ')
    block = src[i:src.index("out.append(", i + 10)]
    assert "markets.npc_placements(markets.load())" in block
    assert '("fn", markets.MERCHANTS_FN), ("wait", 8), ("check", "stall_merchants")' in block
    assert 'kind == "check" and v == "stall_merchants"' in src and "markets.verify(rc)" in src
    doc = M.load()
    files, _ = M.build(doc)
    assert "data/cobblers/function/stalls/merchants/all.mcfunction" in files
    assert M.MERCHANTS_FN == "cobblers:stalls/merchants/all"
    # no dialogue keeper is placed any more, at a stall (2026-10-04) or a counter (2026-10-06): the merchant replaces
    # it (and its town's _clear removes it)
    assert M.stall_placements(doc) == [] and M.npc_placements(doc) == []
    ms = M.stall_merchants(doc)
    assert sorted(m["stall"] for m in ms) == sorted([s["id"] for s in M.emitted_stalls(doc)] + [c["id"] for c in M.emitted(doc)])
    assert len({m["tag"] for m in ms}) == len(ms)
    # 3.5+ blocks between every two keepers the step places, merchants included; so the removal radius (2.5) round a
    # merchant reaches no other keeper
    ks = [(m["stall"], m["at"]) for m in ms]
    for a in range(len(ks)):
        for b in range(a + 1, len(ks)):
            assert math.dist(ks[a][1], ks[b][1]) >= M.NPC_CLEAR, (ks[a][0], ks[b][0])
