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


def _place(doc, g=None):
    out, _res = D.files(doc, g or FlatGround())
    return out["data/cobblers/function/direct_trades/place.mcfunction"]


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
    placed = [o["id"] for o in doc["experiment_offers"]] + [ln["id"] for ln in doc["lines"] if ln["approved"] is True]
    assert len(rs) == len(placed)
    for oid, r in zip(placed, rs):
        tail = CONTROL_TAIL if oid == "exp_control_multiplier" else FIXED_TAIL
        assert tail in r, (oid, r)


def test_the_experiment_recipes_are_the_ones_authored(doc):
    rs = _recipes(_summon(_place(doc)))
    assert rs[0].startswith('{buy:{id:"cobblemon:poke_ball",count:4},buyB:{id:"cobblemon:great_ball",count:1},'
                            'sell:{id:"cobblemon:great_ball",count:1},')
    assert rs[1].startswith('{buy:{id:"cobblemon:poke_ball",count:4},sell:{id:"cobblemon:poke_ball",count:1},')


def test_held_lines_are_not_placed(doc):
    assert all(ln["approved"] is False and ln["status"] == "proposal" for ln in doc["lines"])
    text = _place(doc)
    for ln in doc["lines"]:
        assert ln["sell"]["id"] not in text, ln["id"]
    assert len(_recipes(_summon(text))) == len(doc["experiment_offers"])


def test_an_approved_line_is_placed_and_only_it(doc):
    d = copy.deepcopy(doc)
    mb = next(ln for ln in d["lines"] if ln["id"] == "master_ball")
    mb["approved"], mb["status"] = True, "approved"
    text = _place(d)
    rs = _recipes(_summon(text))
    assert len(rs) == len(d["experiment_offers"]) + 1
    assert rs[-1].startswith('{buy:{id:"minecraft:diamond_block",count:1},buyB:{id:"minecraft:netherite_ingot",count:4},'
                             'sell:{id:"cobblemon:master_ball",count:1},' + FIXED_TAIL)
    for ln in d["lines"]:
        if ln["id"] != "master_ball":
            assert ln["sell"]["id"] not in text, ln["id"]


def test_edges_list_every_line_held_or_placed(doc):
    e = {x["id"]: x for x in D.edges(doc)}
    assert set(e) == {o["id"] for o in doc["experiment_offers"]} | {ln["id"] for ln in doc["lines"]}
    assert e["master_ball"]["placed"] is False
    assert e["master_ball"]["inputs"] == [{"id": "minecraft:diamond_block", "count": 1},
                                          {"id": "minecraft:netherite_ingot", "count": 4}]
    assert e["exp_two_inputs"]["placed"] is True


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
    d["lines"][0]["approved"] = True
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


def test_the_step_holds_the_chunk_and_runs_place(doc):
    assert D.steps(doc) == [("cmd", "forceload add 3632 6460 3636 6464"), ("wait", 3), ("fn", "cobblers:direct_trades/place"),
                            ("wait", 7), ("cmd", "forceload remove 3632 6460 3636 6464")]


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
