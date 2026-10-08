"""tools/economy_audit.py: the independent audit of the Mart tiers, the material exchange and the Bank's buy list.

Written by an agent that built none of the three. Three kinds of test:
  - synthetic fixtures with hand-computable answers (the arbitrage engine, the tier rule, the SNBT reader), so the
    audit's own arithmetic is proved on something other than the data it judges;
  - the real data: today's FAILURE set must equal KNOWN exactly (a known defect that disappears fails, naming it);
  - generator mutations: tools/markets.py, tools/bank.py and tools/traders.py are loaded with one line of their CODE
    changed (the data untouched), and the audit must go red. A record-side mutation would move the expectation with
    the output; these do not.

The jar-backed parts (recipes, ids, the shopkeeper templates and the Mart shelves) need the offline server snapshot
and the vanilla jar; without them those tests skip and say so. What none of this covers: anything in a running game
(a purchase or a Bank sale completing, races, duplication) -- see the audit's own docstring.
"""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import economy_audit as E  # noqa: E402

SNAP = E.default_server_dir()
VANILLA = E.default_vanilla_jar()
HAVE_SNAP = bool(SNAP) and Path(SNAP).is_dir()
HAVE_JARS = HAVE_SNAP and bool(VANILLA) and Path(VANILLA).is_file()
needs_snap = pytest.mark.skipif(not HAVE_SNAP, reason="no offline server snapshot (COBBLERS_SNAPSHOT_DIR)")
needs_jars = pytest.mark.skipif(not HAVE_JARS, reason="no snapshot + vanilla jar (COBBLERS_VANILLA_JAR)")

# Defects the audit finds today: {failure-line prefix: why it is known}. Empty on 2026-10-06: the audit found no
# arbitrage, no tier leak and no missing id. A defect that appears must be fixed or entered here; an entry whose
# defect disappears fails test_the_failure_set_is_exactly_the_known_defects by name.
KNOWN: dict = {}
# Emptied again 2026-10-08, each removal confirmed fixed rather than unseen:
#  - the 28 "AFK BANK <item>:" entries (brewed medicines, the six vitamins, PP Up, revives, pot dishes,
#    emerald_block, gold_ingot): baba770 took each out of the Bank (base_removed / buys_removed, joined to
#    afk_rule.crafts); none of the 28 is in the emitted bank (bank_entries_emitted), and the AFK rule still bites
#    (test_a_generator_that_buys_a_vitamin_again_fails_the_afk_rule, ..._buys_a_berry_again_...).
#  - the eight "BUYER <crate>: a sale that took the crate can return before counting it" entries: ca1ce73 counts the
#    crate straight after the exact take gate, and a short take counts it in short_take; the audit's check is unchanged.
BUYER_FAIL_OPEN = "a sale that took the crate can return before counting it against the allowance"


@pytest.fixture(scope="module")
def real():
    return E.audit(SNAP if HAVE_SNAP else None, VANILLA if HAVE_JARS else None, use_jars=HAVE_JARS)


def mutant(name, old, new=None, *more):
    """tools/<name>.py with source text changed, loaded as a fresh module (the file on disk is untouched). Either
    mutant(name, old, new) or mutant(name, (old, new), (old, new), ...), the replacements applied in order; each target
    must occur exactly once."""
    pairs = [(old, new)] if isinstance(old, str) else [old] + ([new] if new is not None else []) + list(more)
    path = ROOT / "tools" / ("%s.py" % name)
    src = path.read_text(encoding="utf-8")
    for a, b in pairs:
        assert src.count(a) == 1, "the mutation target moved in tools/%s.py: %r" % (name, a)
        src = src.replace(a, b)
    mod = types.ModuleType("%s_mutant" % name)
    mod.__file__ = str(path)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


# ------------------------------------------------------------------------------------------- synthetic fixtures
def _sale(item, unit, sited=True):
    return E.Sale("shop", None, item, unit, True, sited)


# Without it the arbitrage engine could miss a craft chain: 3 wheat at $1 make a bread worth $5 at the Bank ($3 < $5).
def test_a_craft_chain_from_bought_inputs_is_arbitrage():
    conv = [("x:bread", "crafting_shapeless", [({"m:wheat"}, 3)], "m:bread", 1)]
    best = E.cheapest([_sale("m:wheat", 1.0)], conv)
    assert best["m:bread"][0] == 3.0
    fails, reps = E.arbitrage({"m:bread": 5}, best)
    assert len(fails) == 1 and fails[0].startswith("ARBITRAGE m:bread") and "$3.00" in fails[0]
    assert reps == []


# Without it a recipe's output count would be ignored: 1 log ($8) -> 4 planks is $2 a plank, so a $2 Bank price is
# break-even (reported) and a $3 one is arbitrage.
def test_a_recipe_output_count_divides_the_cost():
    conv = [("x:planks", "crafting_shapeless", [({"m:log"}, 1)], "m:planks", 4)]
    best = E.cheapest([_sale("m:log", 8.0)], conv)
    assert best["m:planks"][0] == 2.0
    assert E.arbitrage({"m:planks": 2}, best)[0] == [] and len(E.arbitrage({"m:planks": 2}, best)[1]) == 1
    assert len(E.arbitrage({"m:planks": 3}, best)[0]) == 1


# Without it an unpriceable input (not sold anywhere) would be treated as free and invent arbitrage.
def test_a_recipe_with_an_unsold_input_is_not_a_money_path():
    conv = [("x:cake", "crafting_shapeless", [({"m:wheat"}, 3), ({"m:milk"}, 3)], "m:cake", 1)]
    best = E.cheapest([_sale("m:wheat", 1.0)], conv)
    assert "m:cake" not in best
    assert E.arbitrage({"m:cake": 40}, best) == ([], [])


# Without it a two-step chain (smelt then craft) would be missed: ore $2 -> ingot -> 9 ingots make a block worth $20.
def test_a_two_step_chain_is_followed():
    conv = [("x:ingot", "smelting", [({"m:ore"}, 1)], "m:ingot", 1),
            ("x:block", "crafting_shaped", [({"m:ingot"}, 9)], "m:block", 1)]
    best = E.cheapest([_sale("m:ore", 2.0)], conv)
    assert best["m:block"][0] == 18.0
    assert len(E.arbitrage({"m:block": 20}, best)[0]) == 1


# Without it an unsited stall's line would count as for sale today (it is reported, never failed).
def test_an_unsited_sale_is_not_a_money_path_today():
    best = E.cheapest([_sale("m:coal", 1.0, sited=False)], [])
    assert "m:coal" not in best
    assert len(E.unsited_arbitrage({"m:coal": 4}, [_sale("m:coal", 1.0, sited=False)])) == 1


# Without it the tier rule's arithmetic is unproved: a gym town's Mart takes the badges held on the route arriving
# there; an off-path clerk the badges of the nearest route; the hometown 0.
def test_the_independent_tier_rule_on_a_synthetic_road():
    prog = {"flags": [{"id": "gym1_cleared"}, {"id": "gym2_cleared"}],
            "chapters": [{"id": "c1", "unlocked_by": [], "unlocks": ["gym1_cleared"]},
                         {"id": "c2", "unlocked_by": ["gym1_cleared"], "unlocks": ["gym2_cleared"]},
                         {"id": "c3", "unlocked_by": ["gym2_cleared"], "unlocks": []}]}
    assert E.chapter_badges(prog) == {"c1": 0, "c2": 1, "c3": 2}
    line = lambda x0, x1: [{"x": x0, "z": 0}, {"x": x1, "z": 0}]  # noqa: E731
    routes = {"routes": [{"id": "r1", "chapter": "c1", "from_town": "home", "to_town": "g1", "corridor": {"polyline": line(0, 100)}},
                         {"id": "r2", "chapter": "c2", "from_town": "g1", "to_town": "g2", "corridor": {"polyline": line(100, 200)}},
                         {"id": "r3", "chapter": "c3", "from_town": "g2", "to_town": "end", "corridor": {"polyline": line(200, 300)}}]}
    crit = E.critical_routes(prog, routes)
    assert E.independent_tier("g2", {"x": 200, "z": 5}, crit)[0] == 1
    assert E.independent_tier("home", {"x": 0, "z": 5}, crit)[0] == 0
    assert E.independent_tier("off", {"x": 250, "z": 40}, crit)[0] == 2
    # equidistant from two routes: the fewer badges
    assert E.independent_tier("off", {"x": 100, "z": 40}, crit)[0] == 0


# Without it a claimed tier above the road would pass: the synthetic clerk claims 2 where the road gives 1.
def test_a_claimed_tier_above_the_road_is_a_tier_leak():
    prog = {"flags": [{"id": "gym1_cleared"}, {"id": "gym2_cleared"}],
            "chapters": [{"id": "c1", "unlocked_by": [], "unlocks": ["gym1_cleared"]},
                         {"id": "c2", "unlocked_by": ["gym1_cleared"], "unlocks": ["gym2_cleared"]}]}
    routes = {"routes": [{"id": "r1", "chapter": "c1", "from_town": "home", "to_town": "g1",
                          "corridor": {"polyline": [{"x": 0, "z": 0}, {"x": 100, "z": 0}]}},
                         {"id": "r2", "chapter": "c2", "from_town": "g1", "to_town": "g2",
                          "corridor": {"polyline": [{"x": 100, "z": 0}, {"x": 200, "z": 0}]}}]}
    doc = {"stock_policy": {"mart": {"items": ["m:ball"], "tiers": [{"badges": 2, "items": ["m:great"]}]}},
           "traders": [{"id": "g2_mart", "stock": "mart", "settlement": "g2", "position": {"x": 200, "z": 0}}]}
    towns = {"towns": [{"id": "g2", "critical_path": True}]}
    fails, _ = E.tier_checks(doc, {"g2_mart": 2}, {"g2_mart": {"m:ball", "m:great"}}, prog, routes, towns)
    assert any(f.startswith("TIER LEAK g2_mart (g2): claimed tier 2, independent 1") for f in fails)
    assert any("sells m:great (tier 2) above the independent tier 1" in f for f in fails)
    fails, _ = E.tier_checks(doc, {"g2_mart": 1}, {"g2_mart": {"m:ball"}}, prog, routes, towns)
    assert fails == []


# Without it the shop reader could misread the generators' SNBT (a quoted JSON name, a nested item, a typed list).
def test_the_snbt_reader_reads_a_merchant_summon():
    line = ('summon cobbledollars:cobble_merchant 1.5 64 2.5 {CustomName:"{\\"text\\": \\"Hal\\"}",NoAI:1b,'
            'Rotation:[90.0f,0.0f],CobbleMerchantShop:[{Category:"Ore",Offers:[{Item:{count:16,id:"minecraft:coal"},'
            'Price:"480"},{Item:{id:"minecraft:torch",count:1},Price:"5"}]}],Tags:["a","b"]}')
    (kind, nbt), = E.summons([line])
    assert kind == "cobbledollars:cobble_merchant"
    assert nbt["CustomName"] == '{"text": "Hal"}'
    assert E.shop_offers(nbt) == [("Ore", "minecraft:coal", 16, 480), ("Ore", "minecraft:torch", 1, 5)]


# ------------------------------------------------------------------------------------------------ the real data
# Without it a new arbitrage, tier leak or missing id would land silently, and a fixed known defect would linger here.
def test_the_failure_set_is_exactly_the_known_defects(real):
    fails, _reps, _notes = real
    unknown = [f for f in fails if not any(f.startswith(k) for k in KNOWN)]
    gone = [k for k in KNOWN if not any(f.startswith(k) for f in fails)]
    assert not unknown, "new economy failures:\n" + "\n".join(unknown)
    assert not gone, "a KNOWN economy defect no longer occurs; remove its entry: " + ", ".join(gone)


# Without it a stale committed bank.json (what install copies) could disagree with the data and nothing would say so.
def test_the_committed_bank_file_is_the_generators_output():
    assert E.bank_entries_emitted() == E.read_json(E.COMMITTED_BANK)["bank"]


# Without it the arbitrage check could pass vacuously: it must price every id the emitted bank lists and see one offer
# per stock line of every sited counter and stall, read back from markets.py's summons.
def test_the_arbitrage_check_reads_the_world_it_judges(real):
    _f, _r, notes = real
    line = next(n for n in notes if n.startswith("arbitrage:"))
    banks = int(re.search(r"(\d+) bank prices", line).group(1))
    assert banks == len({e["item"] for e in E.bank_entries_emitted()})
    md = E.read_json(E.DATA / "markets.json")
    lines = sum(len(r.get("stock") or []) for r in md["counters"] + md["stalls"] if r.get("status") == "sited")
    assert lines > 0 and len([s for s in E.market_sales() if s.sited]) == lines


# Without it the recipe reader could read nothing and the chain check would be direct sale only: vanilla bread is
# three wheat, and the reader must price it so.
@needs_jars
def test_the_recipe_reader_knows_vanilla_bread():
    conv = E.load_jars(SNAP, VANILLA).conversions()
    bread = [c for c in conv if c[3] == "minecraft:bread" and c[1] == "crafting_shaped"]
    assert bread and bread[0][2] == [({"minecraft:wheat"}, 3)] and bread[0][4] == 1


# Without it an exchange line could go unreported: every exchange_for line in data/markets.json gets one REPORT with
# the dollars its material earns and either an hours ratio or an explicit NOT DERIVABLE.
def test_every_exchange_line_is_reported_with_its_ratio(real):
    _f, reps, _n = real
    md = E.read_json(E.DATA / "markets.json")
    want = sum(1 for c in md["counters"] for ln in c.get("stock") or [] if ln.get("exchange_for"))
    got = [r for r in reps if r.startswith("exchange ")]
    assert want >= 1 and len(got) == want
    for r in got:
        assert "material earns" in r and ("ratio" in r or "NOT DERIVABLE" in r or "NOT EMITTED" in r), r


# Without it the base food prices would leave the report silently: since U1 (2026-10-10) melon, dried kelp, mushroom
# stew and cookies are no longer bought, so each must still be reported with the base's own price (read from the base
# file) and the data/bank.json base_removed line that took it out -- and none of them may be in the emitted bank.
def test_the_afk_report_carries_the_base_food_prices():
    base = {e["item"]: int(e["price"]) for e in E.read_json(E.BASE_BANK)["bank"]}
    bank = E.bank_effective(E.bank_entries_emitted())
    reps = E.afk_report(bank, E.read_json(E.DATA / "bank.json"))
    for item in ("minecraft:melon_slice", "minecraft:dried_kelp", "minecraft:mushroom_stew", "minecraft:cookie"):
        assert item not in bank, "%s is bought again" % item
        line = next(r for r in reps if r.startswith("afk %s " % item))
        assert ("base $%d " % base[item]) in line and "REMOVED" in line, line
        assert re.search(r"data/bank\.json:\d+ base_removed", line), line


# Without it the Mart tiers would be unaudited: with the snapshot, every Mart clerk is tiered and none is a leak.
@needs_snap
def test_no_mart_shelf_runs_ahead_of_its_road(real):
    fails, reps, _n = real
    assert not [f for f in fails if f.startswith("TIER")]
    assert any(r.startswith("reachable early sunset_west_mart") for r in reps)
    assert any(r.startswith("reachable early sea_town_mart") for r in reps)


# --------------------------------------------------------------------------------------------- generator mutations
# Without it the audit might not read markets.py's emission at all: dividing every emitted offer price by 100 (the
# data untouched) makes Cinderlee's coal and the other bought goods cheaper than the Bank pays.
def test_a_cheapening_mutation_in_markets_emission_is_arbitrage():
    m = mutant("markets", '"Price": str(int(it["price"]) // int(it["count"]))}',
               '"Price": str(int(it["price"]) // int(it["count"]) // 100)}')
    fails, _r, _n = E.audit(None, None, markets_mod=m, use_jars=False)
    assert any(f.startswith("ARBITRAGE minecraft:coal") for f in fails), fails[:5]


# Without it the audit might read the data instead of bank.py's output: a x10 on our buy prices inside the generator
# makes the committed file stale and the Bank pay more for coal than a stall charges.
def test_an_inflating_mutation_in_bank_emission_is_caught():
    b = mutant("bank", '"price": b["price"]} for b in doc["buys"]]', '"price": b["price"] * 10} for b in doc["buys"]]')
    fails, _r, _n = E.audit(None, None, bank_mod=b, use_jars=False)
    assert any(f.startswith("STALE BANK") for f in fails)
    assert any(f.startswith("ARBITRAGE minecraft:coal") for f in fails), fails[:5]


# Without it the tier check might agree with any tier the builder computes: raising every gym town's tier by one inside
# traders.mart_tiers (the data untouched) must be a tier leak at the gym-town Marts.
@needs_snap
def test_a_tier_raising_mutation_in_traders_is_a_tier_leak():
    t = mutant("traders", 'crit[tid] = max(0, t["order"] - 1)', 'crit[tid] = max(0, t["order"])')
    fails, _r, _n = E.audit(SNAP, None, use_jars=False, traders_mod=t)
    leaks = [f for f in fails if f.startswith("TIER LEAK")]
    assert any(f.startswith("TIER LEAK gym8_mart (gym8_town): claimed tier 8, independent 7") for f in leaks), leaks[:5]


# Without it the id check could be vacuous: an id no jar carries, emitted by a mutated markets.py, must fail as ours.
@needs_jars
def test_an_unknown_id_in_markets_emission_is_a_missing_id():
    m = mutant("markets", '"Offers": [{"Item": {"count": 1, "id": it["item"]}',
               '"Offers": [{"Item": {"count": 1, "id": it["item"] + "_nonexistent"}')
    fails, _r, _n = E.audit(SNAP, VANILLA, markets_mod=m, use_jars=True)
    assert any(f.startswith("MISSING ID minecraft:coal_nonexistent") for f in fails), fails[:5]


# ------------------------------------------------------------------------------------------------ barter edges
# The barter tests below were written by the A4 auditor, not the builder of tools/direct_trades.py. They prove the
# audit's barter arithmetic on synthetic edges, then read the real data and the real generator, then mutate the
# generator's CODE. They do not prove that a villager trades, keeps its offers or holds its price in a running game:
# that is EXP-055.
FIX = "uses:0,maxUses:9999,rewardExp:0b,specialPrice:0,demand:0,priceMultiplier:0.0f,xp:0"


def _doc(offers=(), lines=()):
    return {"fixed_trade": {"uses": 0, "maxUses": 9999, "rewardExp": False, "specialPrice": 0, "demand": 0,
                            "priceMultiplier": 0.0, "xp": 0},
            "experiment_offers": list(offers), "lines": list(lines)}


def _off(oid, buy, sell, buy_b=None, **kw):
    o = {"id": oid, "buy": {"id": buy[0], "count": buy[1]}, "sell": {"id": sell[0], "count": sell[1]}}
    if buy_b:
        o["buyB"] = {"id": buy_b[0], "count": buy_b[1]}
    o.update(kw)
    return o


def _stub(*recipes):
    """A stand-in for tools/direct_trades.py whose place function summons one villager with these SNBT recipes."""
    text = 'summon minecraft:villager 0.5 64 0.5 {NoAI:1b,Offers:{Recipes:[%s]},Tags:["t"]}\n' % ",".join(recipes)
    return types.SimpleNamespace(files=lambda doc, g: ({"data/t/function/p.mcfunction": text}, {}))


# Without it a barter whose output the Bank buys would not be a loop: buy m:a at $10, barter 1 m:a for 1 m:b, sell
# m:b for $15. A dollar comes back for 10/15 of a dollar.
def test_a_barter_from_bought_inputs_to_a_bank_bought_output_is_a_money_loop():
    b = E.Barter("x", "placed", [("m:a", 1)], (("m:a", 1), None), ("m:b", 1))
    g = E.gains({E.MONEY}, [b.conversion()], [_sale("m:a", 10.0)], {"m:b": 15})
    assert set(g) == {E.MONEY} and abs(g[E.MONEY][0] - 10 / 15) < 1e-9
    assert E.gains({E.MONEY}, [], [_sale("m:a", 10.0)], {"m:b": 15}) == {}


# Without it an item cycle with no money in it would pass: a block crafts into 9 gems and the barter gives a block for
# 8 gems, so one block comes back for 8/9 of a block.
def test_an_item_cycle_through_a_barter_and_a_recipe_is_a_loop():
    conv = [("x:gems", "crafting_shapeless", [({"m:block"}, 1)], "m:gem", 9)]
    b = E.Barter("x", "proposal", [("m:gem", 8)], (None, ("m:gem", 8)), ("m:block", 1))
    g = E.gains({"m:block", "m:gem"}, conv + [b.conversion()], [], {})
    assert abs(g["m:block"][0] - 8 / 9) < 1e-9 and abs(g["m:gem"][0] - 8 / 9) < 1e-9
    assert E.gains({"m:block", "m:gem"}, conv, [], {}) == {}


# Without it a cost A would be counted as authored: Hero of the Village and reputation can bring it down to the
# clamp's floor of 1, so "4 m:p for 2 m:p" looks like a loss as written and is a gain of one at the worst case.
def test_a_cost_a_counts_as_one_and_a_cost_b_as_authored():
    (b,) = E.barter_data(_doc(offers=[_off("e", ("m:p", 4), ("m:p", 2))]))
    assert b.pays == [("m:p", 1)]
    assert abs(E.gains({"m:p"}, [b.conversion()], [], {})["m:p"][0] - 0.5) < 1e-9
    (c,) = E.barter_data(_doc(lines=[_off("l", ("m:a", 3), ("m:o", 1), buy_b=("m:b", 5), status="proposal")]))
    assert c.group == "proposal" and c.pays == [("m:a", 1), ("m:b", 5)]


# Without it a loop that needs an input nobody sells would be called money from nothing: m:x is gathered, not bought,
# so selling the barter's output is income from gathering (B1 holds), not a loop.
def test_an_unbought_input_breaks_the_money_loop():
    b = E.Barter("x", "placed", [("m:a", 1), ("m:x", 2)], (("m:a", 1), ("m:x", 2)), ("m:b", 1))
    assert E.gains({E.MONEY, "m:a", "m:x", "m:b"}, [b.conversion()], [_sale("m:a", 10.0)], {"m:b": 100}) == {}


# Without it the placed group could be read from the data's word instead of what the villager offers, and a missing
# fixed field (maxUses defaults to 4, xp to 1, rewardExp to true) would pass.
def test_the_emitted_villager_must_be_exactly_the_placed_offers_with_every_fixed_field():
    doc = _doc(offers=[_off("e", ("m:p", 4), ("m:g", 1), buy_b=("m:g", 1))])
    good = '{buy:{id:"m:p",count:4},buyB:{id:"m:g",count:1},sell:{id:"m:g",count:1},%s}' % FIX
    f, _r, _n = E.barter_checks([], [], {}, {}, doc=doc, dt_mod=_stub(good))
    assert f == [], f
    missing = good.replace(",priceMultiplier:0.0f", "")
    f, _r, _n = E.barter_checks([], [], {}, {}, doc=doc, dt_mod=_stub(missing))
    assert any(x.startswith("BARTER EMITTED e omits priceMultiplier") for x in f), f
    moved = good.replace("maxUses:9999", "maxUses:4")
    f, _r, _n = E.barter_checks([], [], {}, {}, doc=doc, dt_mod=_stub(moved))
    assert any(x.startswith("BARTER EMITTED e writes maxUses") for x in f), f
    extra = '{buy:{id:"m:q",count:1},sell:{id:"m:r",count:1},%s}' % FIX
    f, _r, _n = E.barter_checks([], [], {}, {}, doc=doc, dt_mod=_stub(good, extra))
    assert any(x.startswith("BARTER EMITTED an offer no placed data offer authors") for x in f), f
    f, _r, _n = E.barter_checks([], [], {}, {}, doc=doc, dt_mod=_stub())
    assert any(x.startswith("BARTER NOT EMITTED e") for x in f), f


# Without it a gain the recipes already had would be blamed on the barter, or a barter gain hidden behind it: a recipe
# dupe (1 m:a -> 2 m:a) is reported as pre-existing; a placed barter gain on another item fails as placed; a proposal
# gain fails as proposal.
def test_gains_are_attributed_to_the_recipes_the_placed_villager_or_the_proposals():
    conv = [("x:dupe", "crafting_shapeless", [({"m:d"}, 1)], "m:d", 2)]
    doc = _doc(offers=[_off("e", ("m:b", 1), ("m:b", 2))],
               lines=[_off("l", ("m:c", 1), ("m:c", 3), status="proposal", approved=False),
                      _off("k", ("m:d", 1), ("m:e", 1), status="proposal", approved=False)])
    rec = '{buy:{id:"m:b",count:1},sell:{id:"m:b",count:2},%s}' % FIX
    f, r, _n = E.barter_checks([], conv, {}, {}, doc=doc, dt_mod=_stub(rec))
    assert any(x.startswith("barter pre-existing gain m:d") for x in r), r
    assert not any(" m:d:" in x for x in f), f
    assert any(x.startswith("BARTER LOOP (placed) m:b") for x in f), f
    assert any(x.startswith("BARTER LOOP (proposal) m:c") for x in f), f
    assert not any(x.startswith("BARTER LOOP (placed) m:c") for x in f)


# Without it the play-loop rules would go unreported: B1 every input bought, B2 a farmed input, B3 a Bank-bought
# output, B4 a cost A over 1 on a line.
def test_the_play_loop_rules_are_reported_per_line():
    doc = _doc(lines=[_off("l", ("minecraft:iron_ingot", 2), ("m:o", 1), buy_b=("m:x", 1), status="proposal")])
    sales = [_sale("minecraft:iron_ingot", 5.0), _sale("m:x", 1.0)]
    _f, r, _n = E.barter_checks(sales, [], {"m:o": 3}, E.cheapest(sales, []), doc=doc, dt_mod=_stub())
    for rule in ("B1", "B2", "B3", "B4"):
        assert any(x.startswith("barter rule %s (proposal) l" % rule) for x in r), (rule, r)


# Without it the audit could read no barter at all and pass: today's data carries 2 experiment offers placed and 8
# proposal lines (counted here from data/direct_trades.json, not from the audit), and every one gets a REPORT line.
def test_the_real_barter_edges_are_all_read(real):
    _f, reps, notes = real
    doc = E.read_json(E.DIRECT_TRADES)
    live = [ln for ln in doc["lines"] if ln.get("approved") is True or ln.get("status") == "approved"]
    placed, proposal = len(doc["experiment_offers"]) + len(live), len(doc["lines"]) - len(live)
    note = next(n for n in notes if n.startswith("barter:"))
    assert note.startswith("barter: %d placed offer(s) read from the emitted villager, %d proposal line(s)"
                           % (placed, proposal)), note
    for o in doc["experiment_offers"] + doc["lines"]:
        assert any(r.startswith("barter %s (" % o["id"]) for r in reps), o["id"]


# Without it a generator that stops writing priceMultiplier would pass the audit (the codec's default is 0.0, so the
# price would not move, but the offer is no longer the one the data authors and nothing else says so).
def test_a_generator_that_drops_price_multiplier_fails():
    d = mutant("direct_trades", "v = over.get(k, fixed[k])",
               'v = over.get(k, fixed[k])\n        if k == "priceMultiplier":\n            continue')
    fails, _r, _n = E.audit(None, None, use_jars=False, direct_trades_mod=d)
    assert any(f.startswith("BARTER EMITTED exp_two_inputs omits priceMultiplier") for f in fails), fails[:5]


# Without it a generator that pays out one more than authored would pass: the control offer becomes 1 Poke Ball (its
# worst-case cost A) for 2, a loop in Poke Balls through the placed villager.
def test_a_generator_that_raises_the_output_count_is_a_placed_loop():
    d = mutant("direct_trades", 'r["sell"] = _cost(offer["sell"])',
               'r["sell"] = dict(_cost(offer["sell"]), count=int(offer["sell"]["count"]) + 1)')
    fails, _r, _n = E.audit(None, None, use_jars=False, direct_trades_mod=d)
    assert any(f.startswith("BARTER LOOP (placed) cobblemon:poke_ball") for f in fails), fails[:5]


# Without it a generator that places held lines would pass: every proposal line would reach the villager unapproved.
# Since 2026-10-08 every real line is approved, so one is held on an in-memory copy of the data (the file is untouched)
# and the CODE change is what places it.
def test_a_generator_that_places_held_lines_fails():
    doc = E.read_json(E.DIRECT_TRADES)
    held = doc["lines"][-1]
    held.update(status="proposal", approved=False)
    clean, _r, _n = E.audit(None, None, use_jars=False, direct_trades_doc=doc)
    assert not [f for f in clean if f.startswith("BARTER EMITTED")], clean[:5]
    d = mutant("direct_trades", 'return list(doc["experiment_offers"]) + placed_lines(doc)',
               'return list(doc["experiment_offers"]) + list(doc["lines"])')
    fails, _r, _n = E.audit(None, None, use_jars=False, direct_trades_mod=d, direct_trades_doc=doc)
    assert any(f.startswith("BARTER EMITTED an offer no placed data offer authors") for f in fails), fails[:5]


# Without it a generator that allows a cost A of 2 would go unseen by the economy: the audit reports B4 on the line it
# then emits (a finding, not a failure, unless it makes a loop). The data copy is in memory; the file is untouched.
def test_a_generator_that_allows_a_cost_a_of_two_is_reported_b4():
    d = mutant("direct_trades", 'if int(ln["buy"]["count"]) != 1:', 'if int(ln["buy"]["count"]) > 2:')
    doc = E.read_json(E.DIRECT_TRADES)
    ln = doc["lines"][0]
    ln.update(status="approved", approved=True)
    ln["buy"]["count"] = 2
    fails, reps, _n = E.audit(None, None, use_jars=False, direct_trades_mod=d, direct_trades_doc=doc)
    assert any(r.startswith("barter rule B4 (placed) %s: cost A is 2" % ln["id"]) for r in reps), reps[-5:]
    assert not [f for f in fails if f.startswith("BARTER EMITTED") or f.startswith("BARTER NOT")], fails[:5]


# Without it an approved line paid in bought items for an output the Bank buys dearer would pass: 1 Poke Ball and
# 1 Great Ball (sold at the counters) for a netherite ingot the Bank buys at $900. The real generator, on a copy of the
# data whose last line is replaced by that one, approved (the short list's eight-line cap holds; the file is untouched).
def test_an_approved_line_from_bought_inputs_to_a_dearer_bank_item_is_a_placed_money_loop():
    doc = E.read_json(E.DIRECT_TRADES)
    doc["lines"][-1] = _off("money_machine", ("cobblemon:poke_ball", 1), ("minecraft:netherite_ingot", 1),
                            buy_b=("cobblemon:great_ball", 1), status="approved", approved=True,
                            late_game_why="test", inputs_why="test")
    fails, _r, _n = E.audit(None, None, use_jars=False, direct_trades_doc=doc)
    assert any(f.startswith("BARTER LOOP (placed) $") for f in fails), fails[:5]


# ======================================================================== 2026-10-08: the Training shelf, the band,
# the second barterer. Written by the economy auditor of the MART and EXCH units, which it built neither of. Synthetic
# fixtures first (hand-computable), then the real data, then generator mutations (CODE changed, data untouched).

# Without it the Training shelf's 19 lines are "neither a Mart basic nor a tier line" and the audit cannot tell a
# training line on time from one sold early: the tier table must read both of the data's tables.
def test_the_tier_table_reads_the_mart_and_the_training_tables():
    mart = {"tiers": [{"badges": 1, "items": ["m:heal"]}],
            "training": {"tiers": [{"badges": 2, "items": [{"item": "m:power", "price": 1500}]}]}}
    tier, price, fails = E.tier_table(mart)
    assert tier == {"m:heal": 1, "m:power": 2} and price == {"m:heal": None, "m:power": 1500} and fails == []
    mart["training"]["tiers"][0]["items"].append({"item": "m:heal", "price": 5})
    assert any("m:heal is listed twice" in f for f in E.tier_table(mart)[2])


# Without it a training line sold above the clerk's tier would pass: the synthetic road gives g2 tier 1; a tier-2
# training line there is a leak, a tier-1 one is not.
def test_a_training_line_above_the_claimed_tier_is_a_tier_leak():
    prog = {"flags": [{"id": "gym1_cleared"}, {"id": "gym2_cleared"}],
            "chapters": [{"id": "c1", "unlocked_by": [], "unlocks": ["gym1_cleared"]},
                         {"id": "c2", "unlocked_by": ["gym1_cleared"], "unlocks": ["gym2_cleared"]}]}
    routes = {"routes": [{"id": "r1", "chapter": "c1", "from_town": "home", "to_town": "g1",
                          "corridor": {"polyline": [{"x": 0, "z": 0}, {"x": 100, "z": 0}]}},
                         {"id": "r2", "chapter": "c2", "from_town": "g1", "to_town": "g2",
                          "corridor": {"polyline": [{"x": 100, "z": 0}, {"x": 200, "z": 0}]}}]}
    doc = {"stock_policy": {"mart": {"items": ["m:ball"], "tiers": [],
                                     "training": {"tiers": [{"badges": 1, "items": [{"item": "m:sel", "price": 1}]},
                                                            {"badges": 2, "items": [{"item": "m:mochi", "price": 1}]}]}}},
           "traders": [{"id": "g2_mart", "stock": "mart", "settlement": "g2", "position": {"x": 200, "z": 0}}]}
    towns = {"towns": [{"id": "g2", "critical_path": True}]}
    fails, _ = E.tier_checks(doc, {"g2_mart": 1}, {"g2_mart": {"m:ball", "m:sel", "m:mochi"}}, prog, routes, towns)
    assert fails == ["TIER LEAK g2_mart sells m:mochi (tier 2) at claimed tier 1"], fails


def _price_doc():
    return {"stock_policy": {"mart": {
        "items": ["m:poke_ball"],
        "tiers": [{"badges": 1, "items": ["m:heal"]}, {"badges": 2, "items": ["m:great_ball"]},
                  {"badges": 3, "items": ["m:hyper"]}],
        "training": {"tiers": [{"badges": 1, "items": [{"item": "m:power", "price": 1500}]}]},
        "early_reach_pricing": {"convenience_within": 2, "convenience_markup": 2, "round_to": 100,
                                "traders": {"far_mart": {"reachable_from_badges": 0}}}}}, "traders": []}


PRICE_MKT = {"income_basis": {"cumulative_by_badge": {"1": 500, "2": 900, "3": 2000}}}


def _shelves(**far):
    near = {"m:poke_ball": 200, "m:heal": 150, "m:great_ball": 600, "m:hyper": 1500, "m:power": 1500}
    f = {"m:poke_ball": 200, "m:heal": 300, "m:power": 3000, "m:hyper": 2100}
    f.update(far)
    return {"near_mart": near, "far_mart": f}


# Without it the early-reach band is unaudited. Hand-computed on a clerk reachable at 0 badges, within 2, x2, round
# 100, income through badge 3 = 2,000: a tier-1 heal (normal 150) must be at least 300; the tier-1 power item (authored
# 1,500) at least 3,000; a tier-3 hyper potion (normal 1,500) more than 2,000; and nothing below its normal price.
def test_the_early_reach_band_on_a_synthetic_shelf():
    doc = _price_doc()
    assert E.mart_price_checks(doc, PRICE_MKT, _shelves())[0] == []
    f, _r = E.mart_price_checks(doc, PRICE_MKT, _shelves(**{"m:heal": 299}))
    assert f == ["PRICE CONVENIENCE far_mart sells m:heal (tier 1, reach 0) at $299, under normal $150 x 2 = $300"], f
    f, _r = E.mart_price_checks(doc, PRICE_MKT, _shelves(**{"m:hyper": 2000}))
    assert len(f) == 1 and f[0].startswith("PRICE GATE far_mart sells m:hyper (tier 3, reach 0) at $2000"), f
    f, _r = E.mart_price_checks(doc, PRICE_MKT, _shelves(**{"m:hyper": 1400}))
    assert any(x.startswith("PRICE UNDER far_mart sells m:hyper at $1400, below its normal $1500") for x in f), f
    f, _r = E.mart_price_checks(doc, PRICE_MKT, _shelves(**{"m:power": 2900}))
    assert len(f) == 1 and f[0].startswith("PRICE CONVENIENCE far_mart sells m:power"), f
    sh = _shelves()
    sh["near_mart"]["m:power"] = 1400                    # an ordinary clerk under the authored price
    f, _r = E.mart_price_checks(doc, PRICE_MKT, sh)
    assert any(x.startswith("PRICE training line m:power") for x in f)
    assert any(x.startswith("PRICE UNDER near_mart sells m:power at $1400") for x in f), f


# Without it the band's own premise (nothing in it changes what a player can catch) is unenforced: a tier-2 ball at a
# 0-badge clerk is in the band, so it fails even at the correct x2 price.
def test_a_ball_in_the_convenience_band_fails_the_premise():
    f, _r = E.mart_price_checks(_price_doc(), PRICE_MKT, _shelves(**{"m:great_ball": 1200}))
    assert f == ["CONVENIENCE BALL far_mart sells m:great_ball (tier 2) to a player with 0 badges at $1200: the band's "
                 "premise is that nothing in it changes what a player can catch"], f


# Without it EV_IV_TRAINING.md 4.2's E2 rule rests on the generic arbitrage check, which only REPORTS equality: a
# vitamin at exactly the Bank's 2,500 is a failure here, at 2,600 it is not.
def test_a_vitamin_at_or_under_the_bank_price_fails():
    bank = {"cobblemon:protein": 2500}
    assert E.vitamin_checks({"cobblemon:protein": (2500.0, "x")}, bank)[0]
    assert E.vitamin_checks({"cobblemon:protein": (2600.0, "x")}, bank)[0] == []


def _two_doc():
    doc = _doc(offers=[_off("e", ("m:p", 4), ("m:p", 1))],
               lines=[_off("l", ("m:a", 1), ("m:o", 1), buy_b=("m:b", 5), status="approved", approved=True)])
    doc.update(barterer={"tag": "bt"}, site={"x": 3, "z": 4}, counter_barterer={"tag": "ct"},
               counter_site={"x": 40, "z": 8})
    return doc


E_REC = '{buy:{id:"m:p",count:4},sell:{id:"m:p",count:1},%s}' % FIX
L_REC = '{buy:{id:"m:a",count:1},buyB:{id:"m:b",count:5},sell:{id:"m:o",count:1},%s}' % FIX


def _vill(x, z, tag, *recs):
    return ('summon minecraft:villager %d.5 64 %d.5 {NoAI:1b,Offers:{Recipes:[%s]},Tags:["%s","%s_new"]}'
            % (x, z, ",".join(recs), tag, tag))


def _stub_lines(*lines):
    return types.SimpleNamespace(files=lambda doc, g: ({"data/t/function/p.mcfunction": "\n".join(lines) + "\n"}, {}))


def _emitted_fails(doc, *lines):
    f, _r, _n = E.barter_checks([], [], {}, {}, doc=doc, dt_mod=_stub_lines(*lines))
    return [x for x in f if x.startswith("BARTER EMITTED")]


# Without it the count of villagers is a constant 1 and the second barterer is a failure, or any number passes. The
# data declares two (barterer at site with the experiment offers; counter_barterer at counter_site with the approved
# lines): each must be summoned once, on its site's block, with exactly its own offers.
def test_each_declared_barterer_is_summoned_once_at_its_site_with_its_own_offers():
    doc = _two_doc()
    assert _emitted_fails(doc, _vill(3, 4, "bt", E_REC), _vill(40, 8, "ct", L_REC)) == []
    f = _emitted_fails(doc, _vill(3, 4, "bt", E_REC))
    assert any("1 villager summons; the data declares 2" in x for x in f), f
    f = _emitted_fails(doc, _vill(3, 4, "bt", L_REC), _vill(40, 8, "ct", E_REC))
    assert any(x.startswith("BARTER EMITTED barterer carries 1 offer(s) that are not its own") for x in f), f
    assert any(x.startswith("BARTER EMITTED counter_barterer carries 1 offer(s)") for x in f), f
    f = _emitted_fails(doc, _vill(3, 4, "bt", E_REC), _vill(41, 8, "ct", L_REC))
    assert f == ["BARTER EMITTED counter_barterer summoned at (41.5, 64.0, 8.5), not on its site's block (40, 8)"], f
    f = _emitted_fails(doc, _vill(3, 4, "bt", E_REC), _vill(40, 8, "zz", L_REC))
    assert any("carrying no declared barterer's tag" in x for x in f) and any("tagged ct" in x for x in f), f


# Without it the owner's "an alternative path, not a bypass" is unenforced. 1 block (uncrafts to 9 ingots at $10) +
# 3 ingots is worth $120 to the Bank; against a $130 counter price it is a bypass, against $120 it is not. The Bank
# buying the output for $200 is a premium (goods into more money than the Bank's own prices allow).
def test_a_barter_cheaper_than_its_money_price_is_a_bypass_and_a_bank_premium_fails():
    conv = [("x:unblock", "crafting_shapeless", [({"m:blk"}, 1)], "m:ing", 9)]
    b = E.Barter("l", "placed", [("m:blk", 1), ("m:ing", 3)], (("m:blk", 1), ("m:ing", 3)), ("m:out", 1))
    f, _r = E.barter_value_checks([b], {"lines": []}, conv, {"m:ing": 10}, {"m:out": (130.0, "buy at c for $130")})
    assert f == ["BARTER BYPASS (placed) l: the worst-case inputs are worth $120, under the output's $130 (its cheapest "
                 "money path, buy at c for $130): cheaper than the counter"], f
    f, r = E.barter_value_checks([b], {"lines": []}, conv, {"m:ing": 10}, {"m:out": (120.0, "buy at c for $120")})
    assert f == [] and any(x.startswith("barter value (placed) l: inputs worth $120 against $120") for x in r)
    f, _r = E.barter_value_checks([b], {"lines": []}, conv, {"m:ing": 10, "m:out": 200}, {})
    assert f == ["BARTER PREMIUM (placed) l: the Bank pays $200 for 1 x m:out, inputs worth $120"], f
    v = E.Barter("v", "placed", [("m:ing", 12)], (None, ("m:ing", 12)), ("cobblemon:protein", 1))
    f, _r = E.barter_value_checks([v], {"lines": []}, [], {"m:ing": 10, "cobblemon:protein": 120}, {})
    assert any(x.startswith("BARTER PREMIUM (placed) v") for x in f), "a vitamin at exactly its inputs' worth is E2"


# Without it a step could hold one chunk of two (tonight's earlier Holdfast defect) and the place function's checks
# would read unloaded blocks. x10 and x20 are chunks 0 and 1; a box over 6-14 holds only chunk 0. A hold released
# before a scheduled function's 100 ticks (5 s) are up is also named.
def test_forceload_must_hold_every_chunk_a_step_function_touches():
    files = {"data/n/function/f.mcfunction": "execute if block 10 64 5 #minecraft:air run say a\n"
                                              "execute unless block 20 64 5 #minecraft:air run say b\n"
                                              "schedule function n:g 100t replace\n",
             "data/n/function/g.mcfunction": "kill @e[tag=x]\n"}
    one = [("cmd", "forceload add 6 1 14 9"), ("fn", "n:f"), ("wait", 7), ("cmd", "forceload remove 6 1 14 9")]
    f = E.forceload_checks(files, one)
    assert len(f) == 1 and "touches chunk (1, 0) at (20, 5)" in f[0], f
    both = [("cmd", "forceload add 6 1 24 9"), ("fn", "n:f"), ("wait", 7), ("cmd", "forceload remove 6 1 24 9")]
    assert E.forceload_checks(files, both) == []
    early = [("cmd", "forceload add 6 1 24 9"), ("fn", "n:f"), ("wait", 3), ("cmd", "forceload remove 6 1 24 9")]
    assert any("releases" in x for x in E.forceload_checks(files, early))
    assert any("does not emit" in x for x in E.forceload_checks(files, [("fn", "n:missing")]))


# ------------------------------------------------------------------------------------------------ the real data
# Without it the band check could pass by reading no early-reach shelf. Counted here from data/traders.json: Sunset
# West (reach 0, tier 7) carries every tier line of tiers 1-7 from both tables; within 2 is the convenience band.
@needs_snap
def test_the_early_reach_clerks_are_priced_by_the_band(real):
    fails, reps, _n = real
    assert not [f for f in fails if f.startswith(("PRICE", "CONVENIENCE"))]
    pol = E.read_json(E.DATA / "traders.json")["stock_policy"]["mart"]
    within = pol["early_reach_pricing"]["convenience_within"]
    tiers = [(t["badges"], len(t["items"])) for t in pol["tiers"] + pol["training"]["tiers"] if t["badges"] <= 7]
    conv = sum(n for b, n in tiers if 1 <= b <= within)
    gate = sum(n for b, n in tiers if b > within)
    want = "price bands sunset_west_mart (reach 0): 0 normal, %d convenience, %d income-gated" % (conv, gate)
    assert conv > 0 and gate > 0 and any(r.startswith(want) for r in reps), [r for r in reps if "price bands" in r]


# Without it an approved line could be re-priced under the counter unnoticed: every approved line is valued (inputs
# at the Bank's price, a block through its jar recipe) against the counter, at a ratio of at least 1.
@needs_jars
def test_every_approved_barter_line_is_valued_against_the_counter(real):
    fails, reps, _n = real
    assert not [f for f in fails if f.startswith(("BARTER BYPASS", "BARTER PREMIUM"))]
    doc = E.read_json(E.DIRECT_TRADES)
    for ln in doc["lines"]:
        if ln.get("approved") is True:
            r = next((x for x in reps if x.startswith("barter value (placed) %s: inputs worth" % ln["id"])), None)
            assert r is not None, ln["id"]
            assert float(r.rsplit(": ", 1)[1]) >= 1.0, r


# Without it the Northlight barterer's place function could read its roof in a chunk the step never loads: the real
# function touches both chunks of the 9x9 lightning box (454, 95) and (455, 95), and the real step holds both.
def test_the_real_barter_step_holds_every_chunk_it_reads():
    import direct_trades as DT
    doc = E.read_json(E.DIRECT_TRADES)
    files, _res = DT.files(doc, E._FlatGround())
    counter = files["data/%s/function/%s/counter.mcfunction" % (doc["namespace"], doc["folder"])]
    assert {(454, 95), (455, 95)} <= set(E.touched_chunks(counter))
    assert E.forceload_checks(files, DT.steps(doc)) == []


# --------------------------------------------------------------------------------------------- generator mutations
# Without it the audit might not read traders.py's band: with the x2 markup dropped inside the generator (data
# untouched), Sunset West sells its tier-1 and tier-2 lines at the ordinary price.
@needs_snap
def test_a_generator_that_drops_the_convenience_markup_fails():
    t = mutant("traders", 'markup = erp.get("convenience_markup") or 1', "markup = 1")
    fails, _r, _n = E.audit(SNAP, None, use_jars=False, traders_mod=t)
    assert any(f.startswith("PRICE CONVENIENCE sunset_west_mart sells cobblemon:power_weight") for f in fails), fails[:5]


# Since baba770 the Bank buys no vitamin (all six are in data/bank.json base_removed and afk_rule.crafts), so E2's
# threshold is gone and the vitamin rule reports instead of judging. The property is now that a vitamin cannot come
# back onto the Bank's buy list: bank.py emitting the base protein entry again (its base_removed filter widened for it,
# data/bank.json untouched) must fail the AFK rule, a protein being PP Up + a berry, PP Up a medicinal brew.
_BANK_KEEPS_PROTEIN = ('if e["item"] not in gone]', 'if e["item"] not in gone or e["item"] == "cobblemon:protein"]')


# Without it a vitamin could return to the Bank unseen and become a farm's money printer again.
@needs_jars
def test_a_generator_that_buys_a_vitamin_again_fails_the_afk_rule():
    b = mutant("bank", *_BANK_KEEPS_PROTEIN)
    assert "cobblemon:protein" in {e["item"] for e in E.bank_entries_emitted(b)}
    fails, _r, _n = E.audit(SNAP, VANILLA, bank_mod=b, use_jars=True)
    assert any(f.startswith("AFK BANK cobblemon:protein: the Bank pays $") for f in fails), fails[:5]


# Without it the vitamin rule (EV_IV_TRAINING.md 4.2 E2) would be unproved now the real Bank gives it no threshold:
# the real data reports each vitamin unbought; with the Bank buying protein again (at the base's price) and the
# traders generator shelving one at $2,000 on the tier-1 training lines, the rule fails it.
@needs_snap
def test_a_vitamin_shelved_under_a_bank_price_fails_the_vitamin_rule(real):
    _f, reps, _n = real
    for v in E.VITAMINS:
        assert "vitamin %s: the Bank does not buy it, so E2 has no threshold" % v in reps, v
    b = mutant("bank", *_BANK_KEEPS_PROTEIN)
    pay = E.bank_effective(E.bank_entries_emitted(b))["cobblemon:protein"]
    assert pay > 2000, "the base protein price no longer exceeds the $2,000 shelf: re-derive the shelf price"
    t = mutant("traders", 'out += [(i["item"], int(i["price"])) for i in t.get("items") or []]',
               'out += [(i["item"], int(i["price"])) for i in t.get("items") or []] + '
               '([("cobblemon:protein", 2000)] if t["badges"] == 1 else [])')
    fails, _r, _n = E.audit(SNAP, None, use_jars=False, traders_mod=t, bank_mod=b)
    assert any(f.startswith("VITAMIN cobblemon:protein obtainable for $2000.00, at or under the Bank's $%d" % pay)
               for f in fails), fails[:5]


# Without it a training shelf one tier early would pass: the generator's tier comparison is off by one.
@needs_snap
def test_a_generator_that_shelves_training_a_tier_early_is_a_leak():
    t = mutant("traders", 't["badges"] <= int(tier or 0):\n            out += [(i["item"]',
               't["badges"] <= int(tier or 0) + 1:\n            out += [(i["item"]')
    fails, _r, _n = E.audit(SNAP, None, use_jars=False, traders_mod=t)
    assert any(f.startswith("TIER LEAK gym1_mart sells cobblemon:power_") for f in fails), fails[:5]


# Without it a barter re-priced under the counter inside the generator would pass: cost B at 9/10 of its count makes
# the Master Ball 1 block + 18 ingots, $24,300 against the counter's $27,000.
@needs_jars
def test_a_generator_that_prices_a_barter_at_nine_tenths_is_a_bypass():
    d = mutant("direct_trades", 'r["buyB"] = _cost(offer["buyB"])',
               'r["buyB"] = dict(_cost(offer["buyB"]), count=int(offer["buyB"]["count"]) * 9 // 10)')
    fails, _r, _n = E.audit(SNAP, VANILLA, use_jars=True, direct_trades_mod=d)
    assert any(f.startswith("BARTER BYPASS (placed) emitted:cobblemon:master_ball: the worst-case inputs are worth "
                            "$24300, under the output's $27000") for f in fails), fails[:8]


# Without it a step holding one chunk of two would pass: the Northlight box shrunk to end at the villager's own x.
def test_a_generator_whose_forceload_drops_the_second_chunk_fails():
    d = mutant("direct_trades", 'cbox = "%d %d %d %d" % (cx - r, cz - r, cx + r, cz + r)',
               'cbox = "%d %d %d %d" % (cx - r, cz - r, cx, cz + r)')
    fails, _r, _n = E.audit(None, None, use_jars=False, direct_trades_mod=d)
    assert any(f.startswith("FORCELOAD R18DT runs cobblers:direct_trades/counter, which touches chunk (455, 95)")
               for f in fails), fails[:5]


# Without it the experiment's offers (one with priceMultiplier 0.2) could reach the production barterer players use.
def test_a_generator_that_puts_the_experiment_offers_on_the_production_barterer_fails():
    d = mutant("direct_trades", 'if o["id"] not in ids]', ']')
    fails, _r, _n = E.audit(None, None, use_jars=False, direct_trades_mod=d)
    assert any(f.startswith("BARTER EMITTED counter_barterer carries 2 offer(s) that are not its own")
               for f in fails), fails[:5]


# ============================================================================================ AFK and the Produce Buyer
# (BANKPRODUCE, 2026-10-10.) Fixtures first (a stub jar set and a hand-written buyer pack, every answer computed by
# hand), then the real data, then generator mutations: tools/bank.py and tools/produce_buyer.py with their CODE changed
# and data/ untouched. What none of this covers: that Pasture Loot really rolls a species table (ASSUMED), that a
# campfire pot or brewing stand can run unattended, and anything EXP-061 tests in game (the dialogue, the give, query).
def _afk_dir(tmp_path, mobs=(), items=()):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mobsbegone-blacklist.json").write_text(json.dumps(list(mobs)), encoding="utf-8")
    (tmp_path / "config" / "PastureLoot.json").write_text(json.dumps(
        {"tick_per_minute": 1200, "drop_chance_per_minute": 0.15, "item_blacklist": list(items)}), encoding="utf-8")
    return str(tmp_path)


def _afk_jars():
    j = E.Jars()
    j.aged = {"t:leek"}
    j.loot = {"t:blocks/leek": [{"pools": [{"entries": [{"type": "minecraft:item", "name": "t:leek_item"}]}]}],
              "t:gameplay/fishing": [{"pools": [{"entries": [{"type": "minecraft:loot_table", "value": "t:fish_junk"}]}]}],
              "t:fish_junk": [{"pools": [{"entries": [{"type": "minecraft:alternatives", "children": [
                  {"type": "minecraft:item", "name": "t:bottle"}]}]}]}]}
    j.species = [("t.jar", "t:species/thief", {"amount": 6, "entries": [
        {"item": "t:berry", "quantityRange": "2-4"}, {"item": "t:gem", "percentage": 5.0},
        {"item": "t:hidden", "percentage": 5.0}]})]
    return j


# Without it the farm derivation is unproved: a crop's block loot, a fishing table reached through a nested loot_table
# reference and a species drop are depth 0; a blacklisted drop is not farmable; a brew of two farmed items is depth 1
# and a brew over that depth 2; a recipe with one unfarmed slot is not farmable.
def test_the_afk_farm_set_on_a_stub_jar(tmp_path):
    conv = [("t:brew", "cobblemon:brewing_stand", [({"t:bottle"}, 3), ({"t:leek_item"}, 1)], "t:brew", 3),
            ("t:tonic", "cobblemon:brewing_stand", [({"t:brew"}, 3), ({"t:berry"}, 1)], "t:tonic", 3),
            ("t:ring", "crafting_shaped", [({"t:gem"}, 8), ({"t:unfarmed"}, 1)], "t:ring", 1)]
    farm, _blocked = E.afk_farmable(_afk_jars(), _afk_dir(tmp_path, items=["t:hidden"]), conv)
    assert farm["t:leek_item"][0] == 0 and farm["t:bottle"][0] == 0 and farm["t:berry"][0] == 0
    assert farm["t:gem"][0] == 0 and "t:hidden" not in farm
    assert farm["t:brew"][0] == 1 and farm["t:tonic"][0] == 2
    assert "t:ring" not in farm


# Without it a stated farm whose mob is blacklisted would count as a farm (or a farm whose mob is not, as blocked).
def test_a_stated_farm_needing_only_blacklisted_mobs_is_blocked(tmp_path):
    _farm, blocked = E.afk_farmable(E.Jars(), _afk_dir(tmp_path, mobs=["minecraft:chicken"]), [])
    assert any(b.startswith("afk stated source blocked minecraft:egg:") for b in blocked)
    assert not any("minecraft:wheat" in b for b in blocked)


# Without it the Bank's AFK rule has no teeth: a bought farm item fails; one excepted with a why AND a decision is
# reported; an exception with no decision fails; an unfarmed item is silent; a stale exception is reported.
def test_a_bought_farm_item_fails_unless_excepted_with_a_decision():
    farm = {"t:pie": (1, "craft"), "t:ore": (0, "ranch"), "t:wart": (0, "crop")}
    doc = {"afk_rule": {"exceptions": [{"item": "t:ore", "why": "ore stays flat", "decision": "the owner"},
                                       {"item": "t:wart", "why": "kept", "decision": ""},
                                       {"item": "t:gone", "why": "x", "decision": "y"}]}}
    fails, reps = E.afk_checks({"t:pie": 20, "t:ore": 5, "t:wart": 1, "t:gem": 9}, doc, farm)
    assert sorted(f.split(":")[0] + ":" + f.split(":")[1] for f in fails) == ["AFK BANK t:pie", "AFK BANK t:wart"]
    assert any(r.startswith("afk exception t:ore $5") for r in reps)
    assert any(r.startswith("afk stale exception t:gone") for r in reps)
    assert not any("t:gem" in x for x in fails + reps)


# Without it the ranch money figures rest on an unproved roll: the Thievul shape (a sure entry, then two 5% entries,
# amount 6) takes the sure one once and the first 5% entry with 1 - 0.95^5 = 0.2262191 (five passes after the first);
# a single 50% entry with amount 1 is taken half the time.
def test_the_drop_roll_expectation_by_hand():
    picks = E.expected_picks({"amount": 6, "entries": [{"item": "a"}, {"item": "b", "percentage": 5.0},
                                                       {"item": "c", "percentage": 5.0}]})
    assert picks[0] == pytest.approx(1.0) and picks[1] == pytest.approx(1 - 0.95 ** 5)
    assert E.expected_picks({"amount": "1", "entries": [{"item": "a", "percentage": 50}]}) == [pytest.approx(0.5)]


def _pb_pack(take_first=True, count_n="0", guarded=True, pay_twice=False, sold_late=False):
    leg = ["scoreboard players set #badges t 0",
           "execute if entity @s[advancements={x:flag/g1=true}] run scoreboard players add #badges t 1",
           ("execute unless score @s leg = #badges t run " if guarded else "") + "scoreboard players set @s sold 0",
           "scoreboard players operation @s leg = #badges t",
           "execute if score #badges t matches 0 run scoreboard players set #price t 40",
           "execute if score #badges t matches 0 run scoreboard players set #cap t 40",
           "execute if score #badges t matches 1 run scoreboard players set #price t 0",
           "execute if score #badges t matches 1 run scoreboard players set #cap t 0"]
    take = ["execute store result score #took t run clear @s #x:produce_buyer/crops 32",
            "execute unless score #took t matches 32 run return run tellraw @s \"no\""] + \
        ([] if sold_late else ["scoreboard players add @s sold 1"])
    pay =["execute store result storage x:pb pay.amount int 1 run scoreboard players get #price t",
           "function x:produce_buyer/pay with storage x:pb pay"] * (2 if pay_twice else 1)
    sell = ["execute store result score #now t run time query gametime",
            "execute if score @s cd > #now t run return 0",
            "function x:produce_buyer/leg",
            "execute if score #price t matches ..0 run return run tellraw @s \"closed\"",
            "execute if score @s sold >= #cap t run return run tellraw @s \"spent\"",
            "execute store result score #have t run clear @s #x:produce_buyer/crops %s" % count_n,
            "execute unless score #have t matches 32.. run return run tellraw @s \"short\"",
            "execute store result score #before t run cobbledollars query @s"] + \
        (take + pay if take_first else pay + take) + \
        ["execute store result score #after t run cobbledollars query @s",
         "execute unless score #after t = #want t run return run tellraw @s \"owed\""] + \
        (["scoreboard players add @s sold 1"] if sold_late else [])
    return {"data/x/function/produce_buyer/leg.mcfunction": leg,
            "data/x/function/produce_buyer/pay.mcfunction": ["$cobbledollars give @s $(amount)"],
            "data/x/function/produce_buyer/sell/crops.mcfunction": sell,
            "data/x/tags/item/produce_buyer/crops.json": {"values": ["t:wheat", "t:carrot"]}}


# Without it the buyer reader is unproved: a hand-written correct pack has no failure and its schedule is read back
# ($40 x 40 at 0 badges, nothing at 1: $1,600 a player); a crate that money buys for less than the price is arbitrage
# (32 wheat at $0.50 = $16 against $40: $24 a crate).
def test_the_buyer_reader_on_a_hand_written_pack():
    fails, reps = E.buyer_checks(_pb_pack(), {"t:carrot": (2.0, "buy at s for $2")})
    assert fails == [], fails
    assert any(r.startswith("buyer schedule (emitted): 0 badges $40 x 40, 1 badges $0 x 0; $1600") for r in reps), reps
    fails, _r = E.buyer_checks(_pb_pack(), {"t:wheat": (0.5, "buy at s for $0.5")})
    assert fails == ["BUYER ARBITRAGE crops: a crate of 32 costs $16.00 (t:wheat) and the buyer pays $40: $24.00 a "
                     "crate, inside the allowance -- t:wheat $0.50: buy at s for $0.5"], fails


# Without it a sale that takes and does not pay, counts by taking, pays twice, or resets the allowance on every sale
# would pass: each defect in the hand-written pack is named.
def test_each_buyer_defect_on_a_hand_written_pack_is_named():
    def names(**kw):
        return E.buyer_checks(_pb_pack(**kw), {})[0]
    assert any("it pays before it takes" in f for f in names(take_first=False))
    assert any("dry-run counts" in f for f in names(count_n="32"))
    assert any("allowance reset" in f for f in names(guarded=False))
    assert any("2 pay calls" in f for f in names(pay_twice=True))
    assert any("the cap fails open" in f for f in names(sold_late=True))


# ------------------------------------------------------------------------------------- AFK and the buyer, real data
# Without it the AFK check could pass vacuously: with the jars it must find the excepted ranch ores farmable (each
# reported with its decision) and price the emerald ranch per hour from the species tables.
@needs_jars
def test_the_real_ranch_ores_are_reported_as_open_exceptions_with_money(real):
    _f, reps, notes = real
    assert any(n.startswith("afk: ") for n in notes)
    for item in ("minecraft:diamond", "minecraft:emerald", "minecraft:raw_iron"):
        assert any(r.startswith("afk exception %s " % item) and "ranch_ore" in r for r in reps), item
    assert any(r.startswith("ranch money minecraft:emerald at $400: best thievul, 0.226 a drop") for r in reps)


# Without it the emitted buyer could regress unseen: the real pack has no BUYER failure at all (the fail-open count
# was fixed in ca1ce73), and its schedule sums to the $3,600 a player the design states
# (docs/mechanics/ECONOMY_OVERHAUL.md 2.2), read from the emitted leg function.
def test_the_real_buyer_pack_is_safe_by_its_emitted_lines(real):
    fails, reps, _n = real
    buyer = [f for f in fails if f.startswith("BUYER")]
    assert not buyer, buyer
    assert any(r.startswith("buyer schedule (emitted): ") and r.endswith("$3600 a player over the campaign")
               for r in reps)


# --------------------------------------------------------------------------- AFK and the buyer, generator mutations
# Without it the AFK check might read the record and not bank.py's output: bank.py emitting an oran berry after the
# buys (data/bank.json untouched: the berry stays in buys_removed) must fail as an AFK item.
@needs_jars
def test_a_generator_that_buys_a_berry_again_fails_the_afk_rule():
    b = mutant("bank", 'for b in doc["buys"]]', 'for b in doc["buys"]] + [{"item": "cobblemon:oran_berry", "price": 2}]')
    fails, _r, _n = E.audit(SNAP, VANILLA, bank_mod=b, use_jars=True)
    assert any(f.startswith("AFK BANK cobblemon:oran_berry: the Bank pays $2") for f in fails), fails[:5]


# Without it the base removals could silently come back: bank.py ignoring base_removed must fail every base food.
@needs_jars
def test_a_generator_that_ignores_base_removed_fails_the_afk_rule():
    b = mutant("bank", 'if e["item"] not in gone]', ']')
    fails, _r, _n = E.audit(SNAP, VANILLA, bank_mod=b, use_jars=True)
    for item in ("minecraft:melon_slice", "minecraft:cod", "cobblemon:relic_coin", "minecraft:cake"):
        assert any(f.startswith("AFK BANK %s:" % item) for f in fails), item


# tools/produce_buyer.py sell_lines since ca1ce73: 7. take + exact gate (a short take runs short_take), 8. count the
# crate against the allowance, 9. pay. The anchors are the generator's own source lines, so a moved line fails loudly.
_PB_TAKE = ('        "execute store result score #took %s run clear @s %s %d" % (T, item, n),\n'
            '        "execute unless score #took %s matches %d run return run function %s" % (T, n, fn_id("short_take")),\n')
_PB_COUNT = ('        "# 8. COUNT the crate against the leg\'s allowance before anything below can return: the cap fails closed",\n'
             '        "scoreboard players add @s %s 1" % S["sold"],\n')
_PB_PAY = ('        "# 9. PAY the schedule\'s price, then the balance must have risen by exactly that",\n'
           '        "execute store result storage %s pay.amount int 1 run scoreboard players get #price %s" % (store, T),\n'
           '        "function %s with storage %s pay" % (fn_id("pay"), store),\n')
_PB_CHECK = ('        "execute unless score #after %s = #want %s run return run tellraw @s %s" % (T, T, text(m["pay_failed"], '
             '"red")),\n')


def _crates():
    return {c["id"] for c in E.read_json(E.DATA / "produce_buyer.json")["crates"]}


# Without it the take-before-pay order is unguarded: produce_buyer.py with its pay moved above its take (the count
# kept straight after the take; data untouched) must fail every crate.
def test_a_generator_that_pays_before_it_takes_fails():
    m = mutant("produce_buyer", _PB_TAKE + _PB_COUNT + _PB_PAY, _PB_PAY + _PB_TAKE + _PB_COUNT)
    fails, _r = E.buyer_checks(E.buyer_emitted(m), {})
    assert {f.split()[1].rstrip(":") for f in fails if "it pays before it takes" in f} == _crates(), fails[:4]


# Without it ca1ce73's fix could be undone unseen: produce_buyer.py counting the crate after the balance check again
# (the pre-ca1ce73 order: a misfiring query returns before the count, so the allowance fails open) must fail every crate.
def test_a_generator_that_counts_after_the_pay_check_fails_open():
    m = mutant("produce_buyer", (_PB_COUNT, ""), (_PB_CHECK, _PB_CHECK + _PB_COUNT))
    fails, _r = E.buyer_checks(E.buyer_emitted(m), {})
    assert {f.split()[1].rstrip(":") for f in fails if BUYER_FAIL_OPEN in f} == _crates(), fails[:4]


# Without it a count that takes is unguarded: produce_buyer.py counting with the crate's size instead of 0 removes the
# goods at the count step, before any gate; every crate must fail.
def test_a_generator_whose_count_takes_fails():
    m = mutant("produce_buyer", 'run clear @s %s 0" % (T, item)', 'run clear @s %s %d" % (T, item, n)')
    fails, _r = E.buyer_checks(E.buyer_emitted(m), {})
    assert len([f for f in fails if "dry-run counts" in f]) == len(E.read_json(E.DATA / "produce_buyer.json")["crates"])


# Without it an unguarded allowance reset (a fresh allowance on every sale, unlimited money) would pass.
def test_a_generator_whose_allowance_resets_every_sale_fails():
    m = mutant("produce_buyer", '"execute unless score @s %s = #badges %s run scoreboard players set @s %s 0" % (S["leg"], T, '
               'S["sold"])', '"scoreboard players set @s %s 0" % S["sold"]')
    fails, _r = E.buyer_checks(E.buyer_emitted(m), {})
    assert any(f.startswith("BUYER leg: the allowance reset") for f in fails), fails[:3]
