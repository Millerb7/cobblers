"""The town squares' stall keepers and the closed spend-money gaps (tools/markets.py `stalls`, data/markets.json).

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
    keep = {k[0]: k for k in M.npc_placements(doc, p) + M.stall_placements(doc, p)}
    assert keep["dlg_market_stoneford"][1] == (1745, 139, 3622) and keep["dlg_market_stoneford"][3] == 180
    assert keep["dlg_stall_stoneford_masons_yard"][1] == (1755, 139, 3632)
    assert keep["dlg_market_redbrow"][1] == (4838, 162, 5690)
    # not in the contract: the record's own fallback site
    assert keep["dlg_market_viltri_quay"][1] == tuple(next(c for c in doc["counters"] if c["id"] == "viltri_quay")["at"])
    assert keep["dlg_stall_fenhide_trapper"][1] == tuple(_stall(doc, "fenhide_trapper")["at"])
    # the independent audit reads the same contract by its own route
    assert MA.contract_seats(FIXTURE)["gym1_town_stall_1"] == [1745, 139, 3622, 180]


def test_the_fixture_contract_is_fully_staffed_and_its_themes_reported():
    doc, p = M.load(), M.load_plazas(FIXTURE)
    assert M.stall_problems(doc, _towns(), p) == []
    rep = M.contract_report(doc, p)
    assert any("stoneford_bakehouse" in r and "'fish'" in r for r in rep)
    assert any("viltri_boatwright: stall gym2_town_stall_2 is not seated" in r for r in rep)


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
    assert len(npcs) == len(M.emitted(doc)) + len(M.emitted_stalls(doc))


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


# ------------------------------------------------------------------------------------------------ generator mutation
def test_a_mutated_purchase_generator_is_caught_at_every_stall_purchase(monkeypatch):
    real = M.buy_lines
    monkeypatch.setattr(M, "buy_lines", lambda doc, c, it: [l for l in real(doc, c, it) if "markets/refund" not in l])
    doc = M.load()
    files, _ = M.build(doc, {})
    hit = {p.split(":")[0] for p in M.output_problems(doc, files) if "no refund after a failed give" in p}
    want = {"data/cobblers/function/stalls/%s/%s.mcfunction" % (s["id"], it["id"])
            for s in M.emitted_stalls(doc) for it in s["stock"]}
    assert want and want <= hit


def test_a_mutated_menu_generator_is_caught_at_every_stall(monkeypatch):
    real = M.menu

    def drop_last(doc, c, kind, fn_of):
        conv, quest = real(doc, c, kind, fn_of)
        conv["nodes"][0]["responses"] = conv["nodes"][0]["responses"][1:]
        return conv, quest
    monkeypatch.setattr(M, "menu", drop_last)
    doc = M.load()
    files, _ = M.build(doc, {})
    named = {p.split(":")[0] for p in M.output_problems(doc, files) if "its dialogue offers" in p}
    assert {"stall %s" % s["id"] for s in M.emitted_stalls(doc)} <= named


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
def test_r17m_places_every_built_stall_keeper():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    i = src.index('out.append(("R17M", ')
    block = src[i:src.index("out.append(", i + 10)]
    assert "markets.npc_placements(markets.load())" in block and "markets.stall_placements(markets.load())" in block
    doc = M.load()
    got = {k[2] for k in M.stall_placements(doc)}
    assert got == {"cobblers:npc_stall_%s" % s["id"] for s in M.emitted_stalls(doc)}
    # 3.5+ blocks between every two keepers the step places (reapply's npc step dedupes within 2)
    ks = M.npc_placements(doc) + M.stall_placements(doc)
    for a in range(len(ks)):
        for b in range(a + 1, len(ks)):
            assert math.dist(ks[a][1], ks[b][1]) >= M.NPC_CLEAR, (ks[a][0], ks[b][0])
