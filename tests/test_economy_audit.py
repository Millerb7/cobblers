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


@pytest.fixture(scope="module")
def real():
    return E.audit(SNAP if HAVE_SNAP else None, VANILLA if HAVE_JARS else None, use_jars=HAVE_JARS)


def mutant(name, old, new):
    """tools/<name>.py with one source line changed, loaded as a fresh module (the file on disk is untouched)."""
    path = ROOT / "tools" / ("%s.py" % name)
    src = path.read_text(encoding="utf-8")
    assert src.count(old) == 1, "the mutation target moved in tools/%s.py: %r" % (name, old)
    mod = types.ModuleType("%s_mutant" % name)
    mod.__file__ = str(path)
    exec(compile(src.replace(old, new), str(path), "exec"), mod.__dict__)
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


# Without it N64's relayed base food prices would go unverified: the AFK report must carry the base's own prices for
# melon, dried kelp, mushroom stew and cookies, read from the base file, and say whether data/bank.json overrides them.
def test_the_afk_report_carries_the_base_food_prices():
    base = {e["item"]: int(e["price"]) for e in E.read_json(E.BASE_BANK)["bank"]}
    reps = E.afk_report(E.bank_effective(E.bank_entries_emitted()), E.read_json(E.DATA / "bank.json"))
    for item in ("minecraft:melon_slice", "minecraft:dried_kelp", "minecraft:mushroom_stew", "minecraft:cookie"):
        line = next(r for r in reps if r.startswith("afk %s " % item))
        assert ("$%d " % base[item]) in line and "bank.json:" in line, line


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
