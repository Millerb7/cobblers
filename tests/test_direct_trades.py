"""tools/direct_trades.py: the barterer's summon carries the fixed-trade fields exactly, held lines are never placed.

These are the BUILDER'S tests (wave A unit A4, 2026-10-07). The economy of the lines is NOT checked here: that is the
independent auditor's (tools/economy_audit.py). The expected fixed-trade text below is written out literally from
the vanilla 1.21.1 MerchantOffer codec keys (experiments/EXP-055-direct-trade-villager/README.md 'Fields'), not
taken from the generator.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

np = pytest.importorskip("numpy")
import chunk_look as CL  # noqa: E402
import direct_trades as D  # noqa: E402

# every placed recipe ends with exactly this, in the codec's order; the control overrides priceMultiplier only
FIXED_TAIL = "uses:0,maxUses:9999,rewardExp:0b,specialPrice:0,demand:0,priceMultiplier:0.0f,xp:0}"
CONTROL_TAIL = "uses:0,maxUses:9999,rewardExp:0b,specialPrice:0,demand:0,priceMultiplier:0.2f,xp:0}"


class FlatGround:
    """A flat heightmap at y100, so the pack can be built without the canonical source."""

    def __init__(self, y=100):
        self.y = y

    def __call__(self, x, z):
        return self.y

    def box(self, x0, z0, x1, z1):
        return np.full((z1 - z0 + 1, x1 - x0 + 1), self.y, dtype=int)


@pytest.fixture()
def doc():
    return D.load()


def _place(doc, g=None, fn="place"):
    """The whole look-then-act chain at <fn> (entry, look, act, done: tools/chunk_look.py), in that order."""
    out, _res = D.files(doc, g or FlatGround())
    return "".join(out["data/cobblers/function/direct_trades/%s%s.mcfunction" % (fn, part)]
                   for part in ("", "_look", "_act", "_done"))


def _counter(doc):
    return _place(doc, fn="counter")


def _held(doc, keep=()):
    """A copy with every line but `keep` held back as a proposal."""
    d = copy.deepcopy(doc)
    for ln in d["lines"]:
        if ln["id"] not in keep:
            ln["approved"], ln["status"] = False, "proposal"
    return d


def _summon(text):
    lines = [ln for ln in text.splitlines() if ln.startswith("summon ")]
    assert len(lines) == 1, "exactly one summon"
    return lines[0]


def _recipes(summon):
    body = summon[summon.index("Recipes:[") + len("Recipes:["):]
    return ["{buy:" + r for r in body.split("{buy:")[1:]]


def test_the_summon_carries_every_fixed_trade_field_exactly(doc):
    s = _summon(_place(doc))
    assert s.startswith("summon minecraft:villager 3634.5 91 6462.5 {")
    assert 'VillagerData:{type:"minecraft:plains",profession:"minecraft:armorer",level:5}' in s
    for flag in ("NoAI:1b", "Invulnerable:1b", "PersistenceRequired:1b", "Silent:1b"):
        assert flag in s
    rs = _recipes(s)
    assert len(rs) == len(doc["experiment_offers"])
    for o, r in zip(doc["experiment_offers"], rs):
        tail = CONTROL_TAIL if o["id"] == "exp_control_multiplier" else FIXED_TAIL
        assert tail in r, (o["id"], r)


def test_the_experiment_recipes_are_the_ones_authored(doc):
    rs = _recipes(_summon(_place(doc)))
    assert rs[0].startswith('{buy:{id:"cobblemon:poke_ball",count:4},buyB:{id:"cobblemon:great_ball",count:1},'
                            'sell:{id:"cobblemon:great_ball",count:1},')
    assert rs[1].startswith('{buy:{id:"cobblemon:poke_ball",count:4},sell:{id:"cobblemon:poke_ball",count:1},')


# the owner, 2026-10-08: the re-priced lines go at Northlight's counter; the Holdfast booth stays EXP-055's
def test_the_northlight_barterer_carries_every_approved_line_and_nothing_else(doc):
    s = _summon(_counter(doc))
    assert s.startswith("summon minecraft:villager 7277.5 116 1525.5 {")
    assert 'VillagerData:{type:"minecraft:snow",profession:"minecraft:cartographer",level:5}' in s
    assert 'Tags:["cob_dt_exchange","cob_dt_exchange_new"]' in s
    approved = [ln for ln in doc["lines"] if ln["approved"] is True]
    # derived from the data, not a literal: at least one line and no more than the authored cap (rules.max_lines)
    assert 1 <= len(approved) <= doc["rules"]["max_lines"], len(approved)
    rs = _recipes(s)
    assert len(rs) == len(approved)
    for ln, r in zip(approved, rs):
        assert r.endswith(FIXED_TAIL) or FIXED_TAIL in r, ln["id"]
        assert ('sell:{id:"%s",count:1}' % ln["sell"]["id"]) in r
    assert "cobblemon:poke_ball" not in s
    for ln in approved:
        assert ln["sell"]["id"] not in _place(doc), ln["id"]


def _arena_prize_items():
    """{item id} of every data/arena_fights.json prizes.items contents entry, read here and not through the audit."""
    a = json.loads((ROOT / "data" / "arena_fights.json").read_text(encoding="utf-8"))
    return {c["item"] for p in a["prizes"]["items"] for c in p.get("contents") or []}


def test_every_approved_line_obeys_the_authored_rules(doc):
    # Without it a line could be approved with a discountable cost A, the same item in both slots or a stale status,
    # whatever the count of lines happens to be (rules: buy_count_one, distinct_inputs, max_lines).
    approved = [ln for ln in doc["lines"] if ln["approved"] is True]
    assert approved and len(approved) <= doc["rules"]["max_lines"]
    for ln in approved:
        assert ln["status"] == "approved", ln["id"]
        assert ln["buy"]["count"] == 1, ln["id"]
        assert ln.get("buyB") and ln["buyB"]["id"] != ln["buy"]["id"], ln["id"]
        assert ln["sell"]["count"] == 1, ln["id"]


def test_no_approved_line_sells_an_arena_prize(doc):
    # Without it a once-per-player arena trophy could be bought at the counter again (the owner, 2026-10-09,
    # arena_trophies_not_sold: "A prize you can buy is not a prize").
    prizes = _arena_prize_items()
    assert prizes, "data/arena_fights.json prizes.items lists no item: the check would pass vacuously"
    sold = {ln["id"]: ln["sell"]["id"] for ln in doc["lines"] if ln["approved"] is True}
    assert not {k: v for k, v in sold.items() if v in prizes}, sold


def test_superseded_lines_are_never_placed(doc):
    # Without it a line the owner retired (data/direct_trades.json superseded_lines) could reach the counter again.
    gone = doc.get("superseded_lines") or []
    assert gone, "no superseded_lines: nothing to check"
    assert {ln["id"] for ln in gone}.isdisjoint({ln["id"] for ln in doc["lines"]})
    text = _counter(doc) + _place(doc)
    for ln in gone:
        assert ln.get("approved") is not True, ln["id"]
        assert ln["sell"]["id"] not in text, ln["id"]


def test_held_lines_are_not_placed(doc):
    d = _held(doc)
    for fn in ("place", "counter"):
        text = _place(d, fn=fn)
        for ln in d["lines"]:
            assert ln["sell"]["id"] not in text, (fn, ln["id"])
    assert len(_recipes(_summon(_place(d)))) == len(d["experiment_offers"])
    assert "Recipes:[]" in _counter(d)


def test_an_approved_line_is_placed_and_only_it(doc):
    d = _held(doc, keep=("master_ball",))
    text = _counter(d)
    rs = _recipes(_summon(text))
    assert len(rs) == 1
    assert rs[0].startswith('{buy:{id:"minecraft:netherite_block",count:1},buyB:{id:"minecraft:netherite_ingot",'
                            'count:21},sell:{id:"cobblemon:master_ball",count:1},' + FIXED_TAIL)
    for ln in d["lines"]:
        if ln["id"] != "master_ball":
            assert ln["sell"]["id"] not in text, ln["id"]


def test_edges_list_every_line_held_or_placed(doc):
    e = {x["id"]: x for x in D.edges(doc)}
    assert set(e) == {o["id"] for o in doc["experiment_offers"]} | {ln["id"] for ln in doc["lines"]}
    assert e["master_ball"]["placed"] is True
    assert e["master_ball"]["inputs"] == [{"id": "minecraft:netherite_block", "count": 1},
                                          {"id": "minecraft:netherite_ingot", "count": 21}]
    assert e["exp_two_inputs"]["placed"] is True
    assert {x["id"] for x in D.edges(_held(doc)) if not x["placed"]} == {ln["id"] for ln in doc["lines"]}


# ------------------------------------------------------------------ the price rule (the owner, 2026-10-08)
def test_every_approved_line_is_priced_within_the_band_of_the_counter(doc):
    assert D.pricing_problems(doc) == []
    # the Master Ball, worked by hand: a netherite block (9 x $900) and 21 ingots (x $900) = $27,000, the counter's
    mb = next(ln for ln in doc["lines"] if ln["id"] == "master_ball")
    assert D.line_value(doc, mb) == 9 * 900 + 21 * 900 == 27000
    assert D.reference_price(mb, D.counter_prices()) == 27000


def test_the_old_cheap_master_ball_is_refused(doc):
    d = copy.deepcopy(doc)
    mb = next(ln for ln in d["lines"] if ln["id"] == "master_ball")
    mb["buy"], mb["buyB"] = {"id": "minecraft:diamond_block", "count": 1}, {"id": "minecraft:netherite_ingot", "count": 4}
    probs = D.pricing_problems(d)
    assert any(p.startswith("line master_ball: inputs worth $4680 against a reference of $27000") for p in probs), probs


def test_a_stale_input_value_is_refused(doc):
    d = copy.deepcopy(doc)
    d["pricing"]["values"]["minecraft:netherite_ingot"]["value"] = 200
    assert any("netherite_ingot is 200, its source (bank) says 900" in p for p in D.pricing_problems(d))


# ------------------------------------------------------------------ the guards bite (each mutation must be refused)
def _refused(d, needle):
    with pytest.raises(D.DirectTradeError) as ei:
        D.files(d, FlatGround())
    assert needle in str(ei.value)


def test_a_moving_price_is_refused(doc):
    d = copy.deepcopy(doc)
    d["fixed_trade"]["priceMultiplier"] = 0.05
    _refused(d, "priceMultiplier")


def test_a_missing_fixed_field_is_refused(doc):
    d = copy.deepcopy(doc)
    del d["fixed_trade"]["demand"]
    _refused(d, "no demand")


def test_a_discountable_cost_a_is_refused(doc):
    d = copy.deepcopy(doc)
    d["lines"][0]["buy"]["count"] = 4
    _refused(d, "Hero of the Village")


def test_the_same_item_in_both_slots_is_refused(doc):
    d = copy.deepcopy(doc)
    d["lines"][0]["buy"] = {"id": "minecraft:netherite_ingot", "count": 1}
    _refused(d, "both slots")


def test_approved_without_status_is_refused(doc):
    d = copy.deepcopy(doc)
    d["lines"][0]["status"] = "proposal"
    _refused(d, "disagrees")


def test_an_experiment_offer_that_can_gain_is_refused(doc):
    d = copy.deepcopy(doc)
    d["experiment_offers"][0]["sell"] = {"id": "cobblemon:master_ball", "count": 1}
    _refused(d, "can gain")


def test_a_shallow_booth_is_refused(doc):
    d = copy.deepcopy(doc)
    d["site"]["depth_below_ground"] = 3
    _refused(d, "lowest ground")


# ------------------------------------------------------------------ the booth and the step
def test_the_booth_guards_every_shell_cell_before_carving(doc):
    text = _place(doc)
    lines = text.splitlines()
    guards = [i for i, ln in enumerate(lines) if ln.startswith("execute if block ")]
    assert len(guards) == 5 * 5 * 5 - 3 * 3 * 3
    stop = lines.index("execute if score #breach cob_dt matches 1 run return fail")
    carve = next(i for i, ln in enumerate(lines) if ln.startswith("fill "))
    assert max(guards) < stop < carve < lines.index(_summon(text))
    assert lines[carve] == "fill 3632 90 6460 3636 94 6464 minecraft:stone_bricks hollow"


def test_the_step_runs_both_chains_waits_them_whole_and_reads_both_counts(doc):
    # N155: no step-level forceload (its release would drop a chunk under a chain still looking); each chain holds its
    # own box (below), and the step waits out the longest chain before reading each barterer's count
    assert D.steps(doc) == [("fn", "cobblers:direct_trades/place"), ("fn", "cobblers:direct_trades/counter"),
                            ("wait", 21),
                            ("check", ("chunk_look", "direct_trades_place", 1, "the Holdfast booth's barterer")),
                            ("check", ("chunk_look", "direct_trades_counter", 1, "the Northlight barterer"))]
    assert 21 * 20 >= CL.STEP_TICKS


def test_each_chain_holds_the_box_its_act_reads(doc):
    # the booth's whole 5x5 footprint (z6464 is the next chunk: A4 audit, 2026-10-07) and the roof within reach
    out, _ = D.files(doc, FlatGround())
    fl = lambda fn: [ln for ln in out["data/cobblers/function/direct_trades/%s.mcfunction" % fn].splitlines()
                     if ln.startswith("forceload ")]
    assert fl("place") == ["forceload add 3632 6460 3636 6464"]
    assert fl("place_done") == ["forceload remove 3632 6460 3636 6464"]
    assert fl("counter") == ["forceload add 7273 1521 7281 1529"]
    assert fl("counter_done") == ["forceload remove 7273 1521 7281 1529"]
    chunks = lambda x0, z0, x1, z1: {(cx, cz) for cx in range(x0 // 16, x1 // 16 + 1) for cz in range(z0 // 16, z1 // 16 + 1)}
    assert not chunks(3632, 6460, 3636, 6464) & chunks(7273, 1521, 7281, 1529), "the two chains run at once"


# ------------------------------------------------------------------ the Northlight spot (from the Mart's template)
def test_the_counter_reads_back_the_whole_roof_within_reach_before_the_summon(doc):
    lines = _counter(doc).splitlines()
    roof = [ln for ln in lines if ln.startswith("execute if block ") and ln.split()[4] != "115"]
    assert len(roof) == 9 * 9            # every column within 4 of (7277, 1525)
    cols = {(int(ln.split()[3]), int(ln.split()[5])) for ln in roof}
    assert cols == {(x, z) for x in range(7273, 7282) for z in range(1521, 1530)}
    assert all(int(ln.split()[4]) >= 116 + D.LIGHTNING_CLEARANCE for ln in roof)
    assert "execute if block 7277 115 1525 #minecraft:air run scoreboard players set #counter_breach cob_dt 1" in lines
    assert "execute unless block 7277 116 1525 #minecraft:air run scoreboard players set #counter_breach cob_dt 1" in lines
    assert "execute unless block 7277 117 1525 #minecraft:air run scoreboard players set #counter_breach cob_dt 1" in lines
    stop = lines.index("execute if score #counter_breach cob_dt matches 1 run return fail")
    assert max(i for i, ln in enumerate(lines) if ln.startswith("execute ") and "breach cob_dt 1" in ln) < stop
    assert stop < lines.index(_summon("\n".join(lines)))
    assert not [ln for ln in lines if ln.startswith(("fill ", "setblock "))]


def test_a_spot_whose_reach_leaves_the_roof_is_refused(doc):
    d = copy.deepcopy(doc)
    d["counter_site"]["z"] = 1530          # the reach box runs to z1534, under the porch's open sky
    _refused(d, "within 4 of the counter barterer")


def test_a_spot_inside_a_wall_is_refused(doc):
    d = copy.deepcopy(doc)
    d["counter_site"]["z"] = 1524          # the Mart's own counter
    _refused(d, "is not air")


def test_the_rcon_checks_use_one_selector_each():
    for c in D.rcon_checks():
        assert "][" not in c, c
    assert "data get entity @e[type=minecraft:villager,tag=cob_dt_exchange,limit=1] Offers.Recipes" in D.rcon_checks()


def test_reapply_wires_the_pack():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert text.index('"R18AF"') < text.index('"R18DT"')
    world_local = text[text.index("WORLD_LOCAL = ("):text.index("SPAWN_PACKS = (")]
    assert '"cobblers_direct_trades"' in world_local
    server = text[text.index("SERVER_PACKS = ("):text.index("EXCLUDED = {")]
    assert '"cobblers_direct_trades"' in server
    assert 'add("direct_trades:build", "direct_trades.py", "build")' in text


def test_the_coverage_gate_needs_the_step(doc, tmp_path, monkeypatch):
    import reapply as R
    out, _ = D.files(doc, FlatGround())
    D.write(out, tmp_path / "cobblers_direct_trades")
    monkeypatch.setattr(R, "PACKS", tmp_path)
    assert R.uncovered([]) == ["cobblers_direct_trades (functions in direct_trades)"]
    todo = [("R18DT", "", D.steps(doc))]
    assert R.uncovered(todo) == []
    assert R.unreferenced(todo) == []


def test_the_real_site_on_the_heightmap(doc):
    import ground as G
    try:
        g = G.load()
    except Exception as e:  # the canonical heightmap lives outside the repo (data/notes/source_tree.md)
        pytest.skip("no canonical heightmap here: %s" % e)
    b = D.booth(doc, g)
    assert b["villager"] == (3634, 102, 6462)
    assert b["ground"]["reach_min"] - b["villager"][1] >= D.LIGHTNING_CLEARANCE
