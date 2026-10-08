"""tools/markets_audit.py: the independent audit of the town markets, by an agent that did not build them.

Three layers:
  - the audit's own machinery on synthetic fixtures with hand-computed answers (a made-up jar, a made-up overlay, a
    hand-written purchase function, a made-up plan), so the audit is tested on more than the one surface it audits;
  - the real markets: the data, the pack tools/markets.py builds, the overlay, the keepers R17M places (since
    2026-10-06 every counter's keeper is a CobbleDollars merchant: data/markets.json decisions counters_are_merchants);
  - GENERATOR mutations: tools/markets.py's own functions changed (never data/markets.json), each of which must turn
    the audit red. A mutation that only edited the record would move the expectation with the output.

Not covered here (validity is not runtime behaviour): a keeper's menu in game, a real charge, a real give, the
recipes vanishing after the overlay is installed -- TIERED_GOODS.md 4 G-1..G-6, an experiment under the lock.
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import markets_audit as MA  # noqa: E402

SB = "sophisticatedbackpacks:"


# ================================================================================================ synthetic fixtures
def _jar(path, files, nested=None):
    with zipfile.ZipFile(path, "w") as z:
        for name, body in files.items():
            z.writestr(name, body if isinstance(body, str) else json.dumps(body))
        for name, inner in (nested or {}).items():
            buf = BytesIO()
            with zipfile.ZipFile(buf, "w") as zi:
                for n, b in inner.items():
                    zi.writestr(n, json.dumps(b))
            z.writestr(name, buf.getvalue())


def _cond(item):
    return [{"condition": "sophisticatedcore:item_enabled", "itemRegistryName": item}]


@pytest.fixture()
def jar_dir(tmp_path):
    _jar(tmp_path / "a.jar", {
        "assets/foo/lang/en_us.json": {"item.foo.pack": "Pack", "block.foo.crate": "Crate", "itemGroup.foo": "x"},
        "data/foo/recipe/pack.json": {"result": {"id": "foo:pack"}, "fabric:load_conditions": _cond("foo:pack")},
        "data/foo/recipe/pack_from_crate.json": {"result": {"id": "foo:pack"}},
        "data/foo/recipe/tool.json": {"result": "foo:tool", "fabric:load_conditions": _cond("foo:tool")},
    }, nested={"META-INF/jars/inner.jar": {"assets/bar/lang/en_us.json": {"item.bar.inner": "Inner"}}})
    return tmp_path


# protects A-1: an id is an item only when a jar's lang names it (nested jars too); removing this lets a typo ship
def test_jar_index_reads_items_from_lang_keys_including_nested_jars(jar_dir):
    idx = MA.JarIndex.from_dir(jar_dir)
    assert {"foo:pack", "foo:crate", "bar:inner"} <= idx.items
    assert "foo:x" not in idx.items and "foo:tool" not in idx.items


# protects A-1 for code-named items (TMCraft's TMs have no lang key): an id with an item model AND an item-tag entry is
# an item; a model alone or a tag alone is not. Without the both-rule a stray model would pass a typo, and without the
# rule at all the 23 TM lines would fail although the jar registers them
def test_an_item_with_no_lang_key_needs_both_a_model_and_an_item_tag(tmp_path):
    _jar(tmp_path / "t.jar", {
        "assets/tm/lang/en_us.json": {"item_group.tm.tms": "TMs"},
        "assets/tm/models/item/tm_both.json": {"parent": "item/generated"},
        "assets/tm/models/item/tm_model_only.json": {"parent": "item/generated"},
        "data/tm/tags/item/tm_moves.json": {"values": ["tm:tm_both", "tm:tm_tag_only",
                                                       {"id": "tm:tm_optional", "required": False}]},
        "assets/tm/models/item/tm_optional.json": {"parent": "item/generated"},
    })
    idx = MA.JarIndex.from_dir(tmp_path)
    assert idx.is_item("tm:tm_both")
    assert not idx.is_item("tm:tm_model_only") and not idx.is_item("tm:tm_tag_only")
    assert not idx.is_item("tm:tm_optional"), "an optional tag entry is not a registry fact"


# protects A-3: a second recipe making a switched-off item without the condition is named; removing it lets a
# disabled tier stay craftable through a side recipe
def test_recipe_gate_names_an_unconditioned_side_recipe_and_an_item_no_recipe_makes(jar_dir):
    idx = MA.JarIndex.from_dir(jar_dir, {"foo:pack", "foo:tool", "foo:ghost"})
    probs = MA.recipe_gate_problems({"foo:pack", "foo:tool", "foo:ghost"}, idx)
    assert len(probs) == 2
    assert any("pack_from_crate.json makes foo:pack without" in p for p in probs)
    assert any("no jar recipe makes foo:ghost" in p for p in probs)


BASE = '#c\n[common]\n\t#Disable\n\tenabledItems = ["sophisticatedbackpacks:a|true", "sophisticatedbackpacks:b|true", ' \
       '"other:c|true", "sophisticatedbackpacks:backpack|true"]\n'


def _flip(text, *items):
    for i in items:
        text = text.replace('"%s|true"' % i, '"%s|false"' % i)
    return text


# protects A-2: the overlay may only switch off what a built counter sells; removing it lets an unsold item become
# unobtainable, or a sold one stay craftable
def test_overlay_rules_on_a_made_up_file():
    ok, off = MA.overlay_problems(BASE, _flip(BASE, SB + "a"), {SB + "a", SB + "backpack"})
    assert ok == [] and off == {SB + "a"}
    unsold, _ = MA.overlay_problems(BASE, _flip(BASE, SB + "a", SB + "b"), {SB + "a"})
    assert unsold == ["overlay: %sb has its recipe switched off but no built counter sells it, so it cannot be had" % SB]
    still_on, _ = MA.overlay_problems(BASE, BASE, {SB + "a"})
    assert len(still_on) == 1 and "still on" in still_on[0]
    foreign, _ = MA.overlay_problems(BASE, _flip(BASE, "other:c"), set())
    assert any("not a Sophisticated Backpacks item" in p for p in foreign)
    moved, _ = MA.overlay_problems(BASE, BASE.replace('"other:c|true", ', "").replace("]", ', "other:c|true"]'), set())
    assert any("order" in p for p in moved)
    other_line, _ = MA.overlay_problems(BASE, BASE.replace("#Disable", "#Changed"), set())
    assert any("other than enabledItems" in p for p in other_line)


GOOD = """# a hand-written purchase in the ferry's order (MARKET_GATING 4), price 100, gate g
execute store result score #now m run time query gametime
execute if score @s cd > #now m run return 0
execute unless entity @s[advancements={cobblers:flag/g=true}] run return run tellraw @s {"text":"no"}
execute store result score @s m run cobbledollars query @s
execute unless score @s m matches 100.. run return run tellraw @s {"text":"short"}
scoreboard players operation @s cd = #now m
scoreboard players add @s cd 20
data modify storage t:s charge.amount set value 100
function t:charge with storage t:s charge
execute store result score #after m run cobbledollars query @s
scoreboard players operation #want m = @s m
scoreboard players remove #want m 100
execute unless score #after m = #want m run return run tellraw @s {"text":"failed"}
scoreboard objectives add gave dummy
scoreboard players set @s gave 0
execute store success score @s gave run give @s foo:pack 2
execute unless score @s gave matches 1 run function t:refund with storage t:s charge
execute unless score @s gave matches 1 run return run tellraw @s {"text":"back"}
tellraw @s {"text":"paid"}"""


def _pack(body):
    return {"data/t/function/buy.mcfunction": body, "data/t/function/charge.mcfunction": "$cobbledollars remove @s $(amount)",
            "data/t/function/refund.mcfunction": "$cobbledollars add @s $(amount)"}


def _buy(body, gate="g"):
    return MA.purchase_problems(_pack(body), "t:buy", "foo:pack", 100, 2, gate, {"m", "cd"})


# protects the model itself: a correct sequence passes all scenarios; if this fails, every payment finding is noise
def test_a_correct_purchase_passes_every_scenario():
    assert _buy(GOOD) == []


def _without(body, needle):
    return "\n".join(l for l in body.splitlines() if needle not in l)


# protects "a player who cannot pay gets nothing and loses nothing", one broken step at a time on a hand fixture;
# removing it would let the model pass a sequence that loses a player's money
@pytest.mark.parametrize("label,body,expect", [
    ("no balance check", _without(GOOD, "matches 100.."), "short, on a CobbleDollars that lets remove overdraw"),
    ("no verify", _without(GOOD, "#after m = #want"), "a charge that takes nothing"),
    ("no refund", _without(GOOD, "t:refund"), "a give that fails"),
    ("no gate re-check", _without(GOOD, "advancements="), "a rich player without g"),
    ("no cooldown", _without(GOOD, "if score @s cd"), "submitted twice in one tick"),
    ("give before the charge", GOOD.replace("tellraw @s {\"text\":\"no\"}", "tellraw @s {\"text\":\"no\"}\ngive @s foo:pack 2"),
     "a player $1 short"),
    ("the wrong price charged", GOOD.replace("set value 100", "set value 101"), "a qualifying player"),
    ("the objective created after the store", GOOD.replace("scoreboard objectives add gave dummy\n", ""), "a give"),
])
def test_each_broken_purchase_step_is_caught(label, body, expect):
    probs = _buy(body)
    assert any(expect in p for p in probs), (label, probs)


DLG = {"initializationAction": "q.run_command('tag ' + q.player.uuid + ' remove t1');q.run_command('execute as ' + "
                                "q.player.uuid + ' if entity @s[advancements={cobblers:flag/g=true}] run tag @s add t1');",
       "pages": [{"id": "menu", "input": {"options": [
           {"text": "Pack x2: $100", "isVisible": "return q.player.has_tag('t1');",
            "action": "q.run_command('tag ' + q.player.uuid + ' remove t1');q.run_command('execute as ' + q.player.uuid + "
                      "' if entity @s[advancements={cobblers:flag/g=true}] run tag @s add t1'); (q.player.has_tag('t1')) ? "
                      "{ q.run_command('execute as ' + q.player.uuid + ' at @s run function cobblers:markets/k/pack'); };"},
           {"text": "Free: $5", "action": "q.run_command('execute as ' + q.player.uuid + ' at @s run function "
                                          "cobblers:markets/k/free');"},
           {"text": "Bye", "action": "q.dialogue.close();"}]}}]}
STOCK = [{"id": "pack", "price": 100, "gate": "g"}, {"id": "free", "price": 5, "gate": None}]


def _dlg(d):
    return MA.dialogue_problems("k", {"data/cobblers/dialogues/dlg_market_k.json": json.dumps(d)}, STOCK,
                                lambda it: it["gate"])


# protects the window (MARKET_GATING 4): a gated option is visible only on its flag's tag and re-probes before it
# runs; removing it lets a two-badge player see and buy a five-badge shelf
def test_window_rules_on_a_made_up_dialogue():
    assert _dlg(DLG) == []
    d = json.loads(json.dumps(DLG))
    del d["pages"][0]["input"]["options"][0]["isVisible"]
    assert any("visible to everyone" in p for p in _dlg(d))
    d = json.loads(json.dumps(DLG).replace("flag/g=true}] run tag @s add t1');\", \"pages\"", "flag/h=true}] run tag @s add t1');\", \"pages\""))
    assert any("not on a tag the menu probes from g" in p for p in _dlg(d))
    d = json.loads(json.dumps(DLG))
    d["pages"][0]["input"]["options"][0]["action"] = ("q.run_command('execute as ' + q.player.uuid + ' at @s run "
                                                      "function cobblers:markets/k/pack');")
    assert any("without re-probing" in p for p in _dlg(d))
    d = json.loads(json.dumps(DLG).replace("$100", "$99"))
    assert any("does not show the price" in p for p in _dlg(d))
    d = json.loads(json.dumps(DLG))
    d["initializationAction"] += " t.d.bought = 1;"
    assert any("stateless" in p for p in _dlg(d))


PLAN = {"streets": [{"id": "main", "polyline": [[0, 0], [20, 0]], "width": 5}],
        "anchors": [{"id": "mart", "role": "pokemart", "rect": [30, 0, 40, 10], "facing": "west"}],
        "plaza": {"rect": [10, 5, 25, 15]}}


# protects "no keeper stands in a road or a building": hand-computed distances on a made-up plan; removing it lets a
# keeper block a street or stand inside a wall
def test_keeper_geometry_on_a_made_up_plan():
    kp = lambda at, fps=None, walked=None, others=None: MA.keeper_problems("k", at, PLAN, fps or {}, walked or {},
                                                                          others or [], 3.0)
    assert kp((5, 64, 1)) and "street main" in kp((5, 64, 1))[0]       # centre (5.5, 1.5): 1.5 < 2.5
    assert kp((5, 64, 2)) == []                                         # centre z 2.5: not < 2.5
    assert "anchor lot mart" in kp((35, 64, 5))[0]
    assert "building h" in kp((50, 64, 50), fps={"h": (48, 48, 52, 52)})[0]
    assert "walked line r" in kp((100, 64, 102), walked={"r": [(90, 100), (110, 100)]})[0]   # 2.5 < 3
    assert kp((100, 64, 104), walked={"r": [(90, 100), (110, 100)]}) == []                    # 4.5
    assert "within 2 blocks" in kp((60, 64, 60), others=[("npc", (61, 64, 61))])[0]
    assert kp((60, 64, 60), others=[("npc", (62, 64, 62))]) == []                            # 2.83 and 3.54


# protects "beside its Mart, facing its plaza" (R17M's own claim): removing it lets a keeper stand behind the Mart
# with its back to the town, which is where all eleven stood when this audit was written
def test_frontage_on_a_made_up_plan():
    # the Mart's door faces west (towards x < 30); the plaza is x 10..25
    assert MA.frontage_problems("k", (28, 64, 5), 90, PLAN) == []      # in front, yaw 90 faces -x: towards the plaza
    behind = MA.frontage_problems("k", (42, 64, 5), 90, PLAN)
    assert len(behind) == 1 and "behind its Mart" in behind[0]
    back = MA.frontage_problems("k", (28, 64, 5), -90, PLAN)           # yaw -90 faces +x: the plaza is behind it
    assert len(back) == 1 and "back to its plaza" in back[0]


# protects the curve's income source (ECONOMY_OVERHAUL R1): trainer income is the data's generated basis, re-summed
# here from its own level sums at 0.28125 S^2; without it a hand-edited or relayed figure would price the curve
def test_trainer_income_is_the_generated_basis_re_summed_from_its_level_sums():
    import copy
    doc = MA.read_json(ROOT / "data" / "markets.json")
    inc = MA.trainer_income(doc)
    assert inc == {int(k): v for k, v in doc["income_basis"]["cumulative_by_badge"].items()}
    # by hand, leg 1's 13 level sums: 0.28125 x (7^2 + 19^2 + ... + 56^2) = 0.28125 x 14339 = 4032.8 -> 4033
    assert sum(s * s for s in doc["income_basis"]["level_sums"]["normal"]["1"]) == 14339 and inc[1] == 4033
    edited = copy.deepcopy(doc)
    edited["income_basis"]["cumulative_by_badge"]["3"] += 1                 # one dollar off its own sums
    with pytest.raises(MA.AuditError, match="badge 3"):
        MA.trainer_income(edited)
    roster = copy.deepcopy(doc)
    roster["income_basis"]["level_sums"]["normal"]["5"][0] += 1             # a roster grew, the total did not
    with pytest.raises(MA.AuditError, match="badge 5"):
        MA.trainer_income(roster)
    relayed = copy.deepcopy(doc)
    relayed["income_basis"]["relayed"] = True
    with pytest.raises(MA.AuditError, match="relayed"):
        MA.trainer_income(relayed)


# --------------------------------------------------------------------------------- the R2 curve on a synthetic shelf
# A two-town shelf whose every term is worked out on paper (ECONOMY_OVERHAUL section 7 R2):
#   numerator  home 100 + t1 (200 + group g at its dearest 80) = 380 of convenience, the power line and the stretch
#              line left out, + fights 100 a leg
#   earned     income + produce (50 holding 0 badges, 10 a leg after) + one hour a leg at the tier opened by then:
#              early = 2/h x $10 = 20 (legs 1-2), deep = early + 1/h x $30 = 50 (legs 3-8)
#   badge 1    480 / (641 + 50 + 20 = 711) = 0.675: inside
#   badge 2    580 / (150 + 60 + 40 = 250) = 2.32: outside; fights 200 > income 150: the hard check
#   badge 3    680 / (1000 + 70 + 90 = 1160) = 0.586: outside; with the stretch (1000, from badge 3) 1680 >= 1160
#   badge 4-8  income 100,000: far under the band
SYN_CRIT = {"home": 0, "t1": 1}
SYN_INCOME = {1: 641, 2: 150, 3: 1000, 4: 100000, 5: 100000, 6: 100000, 7: 100000, 8: 100000}
SYN_EFFORT = {"effort_model": {"tiers": {"early": {"from_tiers": ["early"], "opens_leg": 1},
                                         "deep": {"from_tiers": ["early", "deep"], "opens_leg": 3}}},
              "buys": [{"item": "x:ore", "tier": "early", "rate_per_hour": 2, "price": 10},
                       {"item": "x:gem", "tier": "deep", "rate_per_hour": 1, "price": 30}]}
SYN_BLACKOUT = {"money": {"cap": 300, "percent": 20}}                    # ceil(300 x 20 / 100) = 60


def _syn_doc():
    line = lambda i, p, strand="convenience", **kw: dict({"id": i, "item": "x:" + i, "price": p, "strand": strand}, **kw)
    return {"counters": [{"id": "h", "town": "home", "stock": [line("bag", 100)]},
                         {"id": "c1", "town": "t1", "stock": [
                             line("a", 200), line("tm", 99999, "power"),
                             line("g_lo", 50, group="g"), line("g_hi", 80, group="g"),
                             dict(line("crafting_upgrade", 1000, stretch=True), item=SB + "crafting_upgrade")]},
                         {"id": "off", "town": "elsewhere", "stock": [line("far", 5000)]}],
            "curve_rule": {"fight_allowance": {"per_leg": 100, "parts": {"mart": 40, "blackout": 60}},
                           "produce_allowance": {"by_badges_held": {str(b): (50 if b == 0 else 10) for b in range(8)}},
                           "gathering_hours_per_leg": 1}}


def _syn(doc=None, income=SYN_INCOME, effort=SYN_EFFORT, blackout=SYN_BLACKOUT):
    return MA.curve_faults(doc or _syn_doc(), SYN_CRIT, income, effort, blackout)


def _badges(F, words):
    import re
    return sorted(int(re.match(r"curve: after badge (\d)", f).group(1)) for f in F if words in f)


# protects R2's terms: fights, produce and gathering are each read and accumulated from data, by hand above; without
# it a term could be dropped or counted once instead of every leg
def test_curve_terms_accumulate_every_leg_by_hand():
    fights, produce, gather, P = MA.curve_terms(_syn_doc(), SYN_EFFORT, SYN_BLACKOUT)
    assert P == []
    assert fights == {b: 100 * b for b in range(1, 9)}
    assert produce == {1: 50, 2: 60, 3: 70, 4: 80, 5: 90, 6: 100, 7: 110, 8: 120}
    assert gather == {1: 20, 2: 40, 3: 90, 4: 140, 5: 190, 6: 240, 7: 290, 8: 340}


# protects the R2 band, the fights hard check and the stretch check on a shelf worked out by hand; without it the
# band could pass everything, or count the power line, the off-path counter or the whole pick-one group
def test_curve_band_fights_and_stretch_checks_bite_where_the_hand_figures_say():
    F, N = _syn()
    assert _badges(F, "outside 0.65-0.70") == [2, 3, 4, 5, 6, 7, 8]          # badge 1 at 0.675 passes
    assert _badges(F, "fight allowance") == [2]
    assert _badges(F, "with its stretch items") == [2, 3]
    assert any("1:(380+100)/(641+50+20)=0.68" in n for n in N)


# protects "power lines leave it" (R2): a power line priced up by any amount moves nothing; a convenience line does
def test_curve_power_lines_leave_the_numerator_and_convenience_lines_stay():
    base, _n = _syn()
    doc = _syn_doc()
    next(l for l in doc["counters"][1]["stock"] if l["id"] == "tm")["price"] = 10 ** 9
    assert _syn(doc)[0] == base
    doc = _syn_doc()
    next(l for l in doc["counters"][1]["stock"] if l["id"] == "a")["price"] += 1000
    assert 1 in _badges(_syn(doc)[0], "outside 0.65-0.70")                  # 1480 / 711: badge 1 now fails


# protects the inputs the audit does not own: mutating the INPUT (the effort tiers, the blackout file, the declared
# allowance), never the expectation, must move the verdict; without it a term could be a constant
def test_curve_follows_its_inputs_not_constants():
    rich = json.loads(json.dumps(SYN_EFFORT))
    rich["buys"][0]["rate_per_hour"] = 3                                     # early hour 30: badge 1 earned 721
    F, N = _syn(effort=rich)
    assert any("1:(380+100)/(641+50+30)=0.67" in n for n in N)
    F, _n = _syn(blackout={"money": {"cap": 300, "percent": 10}})            # the blackout now charges 30
    assert any("parts.blackout 60 is not data/blackout.json's charge 30" in f for f in F)
    doc = _syn_doc()
    doc["curve_rule"]["fight_allowance"]["per_leg"] = 700                    # parts no longer sum; fights 700 > 641
    F, _n = _syn(doc)
    assert any("sum to 100, not per_leg 700" in f for f in F)
    assert 1 in _badges(F, "fight allowance")
    tie = json.loads(json.dumps(SYN_EFFORT))
    tie["effort_model"]["tiers"]["cave"] = {"from_tiers": ["deep"], "opens_leg": 3}
    F, _n = _syn(effort=tie)
    assert sum("THE tier's rate" in f for f in F) == 6                       # legs 3-8 cannot pick one tier


# protects the stalls' place in R2 (price_policies.curve_scale criterion: "a critical stall's gated ones"): a stall's
# ungated provision on a critical-path town moves nothing however dear; a gated convenience line on it counts (+1000
# at t1: badge 1's 1480 / 711 leaves the band); an off-path stall counts nothing. Without it a gated stall line would
# escape the band, or food would price the road
def test_curve_counts_a_critical_stalls_gated_line_and_never_its_provisions():
    base, _n = _syn()
    stall = lambda town, **kw: {"id": "s", "town": town, "stock": [
        dict({"id": "x", "item": "x:x", "price": 10 ** 6, "strand": "provision"}, **kw)]}
    doc = _syn_doc()
    doc["stalls"] = [stall("t1")]
    assert _syn(doc)[0] == base
    doc["stalls"] = [stall("elsewhere", price=1000, strand="convenience", gate="g1")]
    assert _syn(doc)[0] == base
    doc["stalls"] = [stall("t1", price=1000, strand="convenience", gate="g1")]
    assert 1 in _badges(_syn(doc)[0], "outside 0.65-0.70")


# protects fail-closed placement: a critical-path line of no known strand is named, not silently left out
def test_curve_names_a_line_of_unknown_strand():
    doc = _syn_doc()
    del doc["counters"][1]["stock"][0]["strand"]
    F, _n = _syn(doc)
    assert any("c1/a has strand None" in f for f in F)


# --------------------------------------------------------------------------------- the curve rule on a synthetic shelf
# data/markets.json price_policies.curve_scale worked on paper, with _syn_doc's terms (fights 100 a leg; produce 50,
# 60, 70; gathering 20, 40, 90), band 0.65-0.70 (midpoint 0.675), round_to 50, and income 2000 / 3000 / 6000:
#   leg 1   earned 2000 + 50 + 20 = 2070; 0.675 x 2070 = 1397.25; - fights 100 = 1297.25
#           list shelf: home bag 300 + t1 a 1000 + group g at its dearest 600 + pin 10 = 1910; scale 0.67919
#           bag 203.76 -> 200; a (count 2, so a $100 step) 679.19 -> 700; g_hi 407.51 -> 400; g_lo 271.68 -> 250;
#           pin 6.79 -> 0 steps, raised to the one-step floor 50. Leg 1 costs 200 + 700 + 400 + 50 = 1350
#   leg 2   nothing on the shelf (t2 has no counter)
#   leg 3   earned 6000 + 70 + 90 = 6160; 0.675 x 6160 = 4158; - fights 300 - leg 1's 1350 = 2508
#           list shelf: t3 iron 2000; scale 1.254: iron 2508 -> 2500; the stretch crafting_upgrade (list 1000,
#           affordable_by 3, sold at t1) takes leg 3's scale: 1254 -> 1250
#   the power line and the off-path counter are not on the curve and carry no rule
CR_CRIT = {"home": 0, "t1": 1, "t3": 3}
CR_INCOME = {1: 2000, 2: 3000, 3: 6000, 4: 7000, 5: 8000, 6: 9000, 7: 10000, 8: 11000}


def _cr_doc():
    def line(i, lp, p, count=1, **kw):
        return dict({"id": i, "item": "x:" + i, "count": count, "price": p, "list_price": lp, "strand": "convenience",
                     "price_rule": "curve_scale"}, **kw)
    doc = _syn_doc()
    doc["price_policies"] = {"curve_scale": {"band": [0.65, 0.7], "round_to": 50}}
    doc["counters"] = [
        {"id": "h", "town": "home", "stock": [line("bag", 300, 200)]},
        {"id": "c1", "town": "t1", "stock": [
            line("a", 1000, 700, count=2), line("g_lo", 400, 250, group="g"), line("g_hi", 600, 400, group="g"),
            line("pin", 10, 50), {"id": "tm", "item": "x:tm", "count": 1, "price": 99999, "strand": "power"},
            dict(line("crafting_upgrade", 1000, 1250, stretch=True, affordable_by=3), item=SB + "crafting_upgrade")]},
        {"id": "c3", "town": "t3", "stock": [line("iron", 2000, 2500)]},
        {"id": "off", "town": "elsewhere", "stock": [{"id": "far", "item": "x:far", "count": 1, "price": 5000,
                                                      "strand": "convenience"}]}]
    return doc


def _cr(doc, income=CR_INCOME):
    return MA.curve_price_faults(doc, CR_CRIT, income, SYN_EFFORT, SYN_BLACKOUT)


def _cr_line(doc, iid):
    return next(it for c in doc["counters"] for it in c["stock"] if it["id"] == iid)


# protects the curve rule's arithmetic on a shelf worked by hand: every price above is the rule's, so nothing is named.
# Without it the audit's re-derivation of the rule could be wrong in a way the real data happens to hide
def test_curve_rule_accepts_exactly_the_hand_worked_prices():
    assert _cr(_cr_doc()) == []


# protects "never accept a scaled price the rule does not produce": one step off the rounding, the old list price typed
# back, the floor ignored, a stretch on its own leg's scale, each is named with the rule's figure; and a mispriced leg
# 1 line faults ALONE (leg 3's expectation is built from the rule's leg-1 prices, not the written ones)
@pytest.mark.parametrize("iid, price, needle", [
    ("bag", 250, "h/bag costs $250; price_policies.curve_scale gives list $300 x leg 1's scale 0.6792 = $200"),
    ("a", 680, "c1/a costs $680"),                                           # count 2: a $100 step, 679 -> 700
    ("iron", 2000, "c3/iron costs $2000; price_policies.curve_scale gives list $2000 x leg 3's scale 1.2540 = $2500"),
    ("pin", 0, "c1/pin costs $0"),                                           # under the one-step floor
    ("crafting_upgrade", 1000, "c1/crafting_upgrade costs $1000"),           # leg 1's scale would give 700
])
def test_curve_rule_names_a_price_the_rule_does_not_give(iid, price, needle):
    doc = _cr_doc()
    _cr_line(doc, iid)["price"] = price
    F = _cr(doc)
    assert len(F) == 1 and needle in F[0], F


# protects the rule's reach and its records: a ruled line off the curve, a curve line with no rule, a missing list
# price, a stretch affordable at a badge the ladder does not give, a policy band moved off 0.3's, a leg already over
# the midpoint before its shelf -- each named. Without it the rule could price lines it never reaches, or quietly
# leave a hand-typed price on the curve
def test_curve_rule_names_its_record_faults():
    doc = _cr_doc()
    doc["counters"][3]["stock"][0].update(price_rule="curve_scale", list_price=5000)
    assert any("off/far carries price_rule curve_scale but is not a critical-path convenience line" in f for f in _cr(doc))
    doc = _cr_doc()
    _cr_line(doc, "iron").pop("price_rule")
    assert any("c3/iron is a critical-path convenience line without price_rule curve_scale" in f for f in _cr(doc))
    doc = _cr_doc()
    _cr_line(doc, "bag")["list_price"] = 0
    assert any("h/bag carries price_rule curve_scale with list_price 0" in f for f in _cr(doc))
    doc = _cr_doc()
    _cr_line(doc, "crafting_upgrade")["affordable_by"] = 2
    assert any("affordable_by 2; the ladder makes it affordable at badge 3" in f for f in _cr(doc))
    doc = _cr_doc()
    doc["price_policies"]["curve_scale"]["band"] = [0.6, 0.7]
    assert _cr(doc) == ["curve rule: price_policies.curve_scale.band [0.6, 0.7] is not PROGRESSION_LADDER 0.3's "
                        "[0.65, 0.7]"]
    F = _cr(_cr_doc(), income={**CR_INCOME, 3: 1000})                  # 0.675 x 1160 = 783 < 300 + 1350
    assert any("leg 3:" in f and "no positive scale exists" in f for f in F)


# protects the gate source: a town's badge comes from the gym flag's own town, not from data/markets.json
def test_town_badges_come_from_progression_and_towns():
    tb = MA.town_badges(MA.read_json(ROOT / "data" / "progression.json"), MA.read_json(ROOT / "data" / "towns.json"))
    assert tb["hometown"] == (0, None)
    assert tb["gym3_town"] == (3, "gym3_cleared") and tb["gym8_town"] == (8, "gym8_cleared")
    assert len(tb) == 9


# ================================================================================================ the real markets
@pytest.fixture(scope="module")
def M():
    import markets
    return markets


def _inputs():
    return dict(progression=MA.read_json(ROOT / "data" / "progression.json"),
                towns=MA.read_json(ROOT / "data" / "towns.json"), bank=MA.read_json(MA.BANK),
                base_text=MA.BASE_OVERLAY.read_text(encoding="utf-8"))


def _audit(M, doc=None, overlay_text=None, **kw):
    doc = doc or M.load()
    files, _npcs = M.build(doc)
    i = _inputs()
    return MA.audit(doc, MA.load_pack(files), overlay_text if overlay_text is not None else MA.OVERLAY.read_text(encoding="utf-8"),
                    i["base_text"], i["progression"], i["towns"], i["bank"], **kw)


# protects the whole offline contract on the committed data and the pack built from it (jars and keepers aside);
# removing it leaves the markets unaudited between builds. The R2 curve is held apart (the next test): the committed
# convenience strand was priced for model B and has not been re-priced (U5's builder side)
def test_the_built_markets_pass_the_offline_audit(M):
    F, W, N = _audit(M)
    assert [f for f in F if not f.startswith("curve:")] == [], F
    assert any(n.startswith("curve R2") for n in N)


# protects the R2 band on the committed shelf. It was a strict xfail until the convenience strand was re-priced
# (unit CURVEPRICE, data/markets.json price_policies.curve_scale; the builder removed only the marker)
def test_the_committed_shelf_is_inside_the_r2_band(M):
    F, _w, _n = _audit(M)
    assert [f for f in F if f.startswith("curve:")] == []


# protects the audit's input PATHS: the whole audit, given no effort/blackout, reads data/bank.json and
# data/blackout.json from disk. Pointed at a copy whose rates are all doubled, badge 1's gathering term doubles (the
# early hour, $620 committed); pointed at a blackout charging 10%, the allowance's blackout part is named. Without it
# the terms could be read once into a constant and never follow the files
def test_mutation_the_audit_follows_its_input_files(M, tmp_path, monkeypatch):
    eff = MA.read_json(MA.DATA_BANK)
    for b in eff["buys"]:
        b["rate_per_hour"] *= 2
    (tmp_path / "bank.json").write_text(json.dumps(eff), encoding="utf-8")
    bo = MA.read_json(MA.BLACKOUT)
    bo["money"]["percent"] = 10
    (tmp_path / "blackout.json").write_text(json.dumps(bo), encoding="utf-8")
    early = lambda N: float(next(n for n in N if n.startswith("curve R2")).split("1:(")[1].split(")")[1].split("+")[-1])
    _f, _w, N0 = _audit(M)
    monkeypatch.setattr(MA, "DATA_BANK", tmp_path / "bank.json")
    _f, _w, N1 = _audit(M)
    assert early(N1) == 2 * early(N0) > 0
    monkeypatch.setattr(MA, "BLACKOUT", tmp_path / "blackout.json")
    F, _w, _n = _audit(M)
    assert any("parts.blackout 600 is not data/blackout.json's charge 300" in f for f in F)


# protects R2's split on the REAL shelf: a critical power line (Holdfast's Full Restore) re-priced moves no curve
# figure; a critical convenience line (Holdfast's Inception Upgrade) moves badge 8's numerator by exactly its change
def test_the_real_curve_drops_power_lines_and_counts_convenience_lines(M):
    import copy
    doc = M.load()
    tb = MA.town_badges(MA.read_json(ROOT / "data" / "progression.json"), MA.read_json(ROOT / "data" / "towns.json"))
    crit = {t: n for t, (n, _f) in tb.items()}
    run = lambda d: MA.curve_faults(d, crit, MA.trainer_income(d), MA.read_json(MA.DATA_BANK), MA.read_json(MA.BLACKOUT))
    base = run(doc)
    power = copy.deepcopy(doc)
    fr = _item(power, "holdfast", "full_restore")
    assert fr["strand"] == "power"
    fr["price"] += 50000
    assert run(power) == base
    conv = copy.deepcopy(doc)
    inc = _item(conv, "holdfast", "inception_upgrade")
    assert inc["strand"] == "convenience"
    before = next(n for n in base[1] if n.startswith("curve R2"))
    inc["price"] += 1000
    after = next(n for n in run(conv)[1] if n.startswith("curve R2"))
    assert before.split(" 8:(")[0] == after.split(" 8:(")[0]                  # badges 1-7 untouched
    b8 = lambda n: int(n.split(" 8:(")[1].split("+")[0])
    assert b8(after) - b8(before) == 1000


# protects the committed overlay (what install copies to the server): base plus exactly the sold, built
# Sophisticated Backpacks items switched off; the count is TIERED_GOODS A-2's 26
def test_the_committed_overlay_switches_off_exactly_the_sold_items(M):
    F, _w, _n = _audit(M)
    assert not [f for f in F if f.startswith("overlay")]
    off = {i for i, on in MA.enabled_items(MA.OVERLAY.read_text(encoding="utf-8")) if not on}
    assert len(off) == 26 and all(i.startswith(SB) for i in off)


# --------------------------------------------------------------------------------- generator mutations (A-6)
# Since 2026-10-06 (data/markets.json decisions counters_are_merchants) a counter is a CobbleDollars merchant: the
# purchase and window mutations of the dialogue era went with the generator they mutated (buy_lines, conversation).
# The merchant's generator is mutated instead, data untouched; each must fail at every built counter.
def _built(M):
    return sorted(c["id"] for c in M.load()["counters"] if c.get("status") == "sited")


def _named(F, prefix, needle):
    return sorted({f.split(": ")[1].split(" ")[0].split("/")[0] for f in F if f.startswith(prefix) and needle in f})


# protects the shop against the GENERATOR (tools/markets.py merchant_shop changed): an offer dropped, and every price
# doubled, must each be named at every built counter
def test_a_mutated_shop_generator_is_caught(monkeypatch, M):
    real = M.merchant_shop
    monkeypatch.setattr(M, "merchant_shop", lambda s: [dict(real(s)[0], Offers=real(s)[0]["Offers"][:-1])])
    F, _w, _n = _audit(M)
    assert _named(F, "payment", "times, not once") == _built(M)

    def dear(s):
        cat = real(s)[0]
        return [dict(cat, Offers=[dict(o, Price=str(int(o["Price"]) * 2)) for o in cat["Offers"]])]
    monkeypatch.setattr(M, "merchant_shop", dear)
    F, _w, _n = _audit(M)
    assert _named(F, "payment", "the shelf's line is") == _built(M)


# protects the payment rule "nothing but the screen charges" against the GENERATOR (tools/markets.py merchant_functions
# given back a dialogue-era purchase): a give or a charge anywhere in the pack is named
def test_a_generator_that_charges_beside_the_screen_is_caught(monkeypatch, M):
    real = M.merchant_functions
    monkeypatch.setattr(M, "merchant_functions", lambda doc, pl: dict(real(doc, pl), **{
        "data/cobblers/function/stalls/merchants/extra.mcfunction": ["cobbledollars remove @s 5", "give @s foo:x 1"]}))
    F, _w, _n = _audit(M)
    assert any(f.startswith("payment: data/cobblers/function/stalls/merchants/extra.mcfunction gives or charges")
               for f in F)


# protects the removal against the GENERATOR (tools/markets.py merchant_functions changed): with the dialogue keepers'
# kills gone from the pack, every built counter is named as leaving its Steve beside its merchant
def test_a_generator_that_leaves_the_dialogue_keeper_is_caught(monkeypatch, M):
    real = M.merchant_functions
    monkeypatch.setattr(M, "merchant_functions", lambda doc, pl: {
        k: [x for x in v if "type=cobblemon:npc" not in x] for k, v in real(doc, pl).items()})
    F, _w, _n = _audit(M)
    assert _named(F, "merchant", "a Steve left beside it") == _built(M)


# protects the overlay against the GENERATOR (tools/markets.py disabled_set changed): a sold item left craftable,
# and a never-sold tier switched off, must each be named
def test_a_mutated_overlay_generator_is_caught(monkeypatch, M):
    real = M.disabled_set
    monkeypatch.setattr(M, "disabled_set", lambda doc: [i for i in real(doc) if i != SB + "iron_backpack"])
    F, _w, _n = _audit(M, overlay_text=M.overlay_text(M.load()))
    assert any("%siron_backpack is sold at a built counter but its recipe is still on" % SB in f for f in F)
    monkeypatch.setattr(M, "disabled_set", lambda doc: real(doc) + [SB + "netherite_backpack"])
    F, _w, _n = _audit(M, overlay_text=M.overlay_text(M.load()))
    assert any("netherite_backpack has its recipe switched off but no built counter sells it" in f for f in F)


# protects the keepers against the GENERATOR R17M runs (tools/markets.py stall_merchants changed): every counter's
# merchant moved ten blocks and turned round must be named as a summon that left its data, at every built counter
def test_a_mutated_keeper_placement_is_caught(monkeypatch, M):
    real = M.stall_merchants

    def moved(doc=None, plazas=None):
        out = []
        for m in real(doc, plazas):
            if m["kind"] == "counter":
                m = dict(m, at=(m["at"][0] + 10, m["at"][1], m["at"][2]), data=dict(m["data"], Rotation=[
                    float(m["yaw"]) + 180.0, 0.0]))
            out.append(m)
        return out
    monkeypatch.setattr(M, "stall_merchants", moved)
    doc = M.load()
    files, _ = M.build(doc)
    pack = MA.load_pack(files)
    keepers = MA.pack_keepers(pack, doc, M.MERCHANTS_FN)
    assert sorted(k[0] for k in keepers) == _built(M)
    F, _w, _n = _audit(M, keepers=keepers, placements=MA.read_json(ROOT / "data" / "placements.json"), templates=None,
                       walked={}, others=[])
    assert sum(1 for f in F if "the data sites it at" in f) == len(_built(M))
    assert sum(1 for f in F if "its seat's is" in f) == len(_built(M))


# protects "R17M summons the counters' merchants": the audit reads the step from tools/reapply.py and the summons from
# the functions it runs, never from markets.npc_placements (empty since 2026-10-06)
def test_r17m_runs_the_merchants_and_places_no_dialogue_keeper(M):
    assert MA.r17m_root() == M.MERCHANTS_FN
    pack = MA.load_pack(M.build(M.load())[0])
    assert sorted(k[0] for k in MA.pack_keepers(pack, M.load(), MA.r17m_root())) == _built(M)
    assert not [r for r in pack if r.startswith(("data/cobblers/dialogues/", "data/cobblers/npcs/"))]


# --------------------------------------------------------------------------------- data rules against the design
# (these compare data/markets.json with the ladder, two independent sources, so a record mutation is the right probe)
def _doc_with(M, fn):
    doc = json.loads(json.dumps(M.load()))
    fn(doc)
    return doc


def _item(doc, cid, iid):
    c = next(c for c in doc["counters"] if c["id"] == cid)
    return next(it for it in c["stock"] if it["id"] == iid)


def _drop(it, gate):
    it["gate_dropped"] = dict(it.get("gate_dropped") or {"decision": "counters_are_merchants", "why": "probe"}, gate=gate)


# protects "each town's shelf only adds items at or after its badge", read since 2026-10-06 from the gate each line
# records in gate_dropped (a merchant cannot gate): a shelf recorded below its town's badge, and an off-path shelf on a
# flag the ladder does not give it, are both named
def test_a_gate_off_the_design_is_caught(M):
    doc = _doc_with(M, lambda d: _drop(_item(d, "highwire", "iron_backpack"), "gym2_cleared"))
    F, _w, _n = MA.audit(doc, MA.load_pack(M.build(M.load())[0]), MA.OVERLAY.read_text(encoding="utf-8"),
                         **{k: v for k, v in _inputs().items()})
    assert any("highwire/iron_backpack (town gym3_town) records the gate gym2_cleared" in f for f in F)
    doc = _doc_with(M, lambda d: _drop(_item(d, "fossick", "void_upgrade"), "gym2_cleared"))
    F, _w, _n = MA.audit(doc, MA.load_pack(M.build(M.load())[0]), MA.OVERLAY.read_text(encoding="utf-8"), **_inputs())
    assert any("fossick/void_upgrade" in f and "none or gym3_cleared" in f for f in F)


# protects "a merchant shows every line to every player" (the owner, 2026-10-06: "villagers with ui only"): a counter
# line that still carries a gate is a fault, a dropped gate with no recorded decision is a fault, and every built
# counter the ladder gates is reported as a FINDING (on sale before its badge), not hidden
def test_a_gated_merchant_line_and_an_unrecorded_drop_are_caught_and_the_lost_gates_reported(M):
    doc = _doc_with(M, lambda d: _item(d, "highwire", "magnet").update(gate="gym3_cleared"))
    F, W, _n = MA.audit(doc, MA.load_pack(M.build(M.load())[0]), MA.OVERLAY.read_text(encoding="utf-8"), **_inputs())
    assert any("highwire/magnet is gated on gym3_cleared, but its merchant shows every line" in f for f in F)
    doc = _doc_with(M, lambda d: _item(d, "highwire", "magnet")["gate_dropped"].update(decision="nobody"))
    F, W, _n = MA.audit(doc, MA.load_pack(M.build(M.load())[0]), MA.OVERLAY.read_text(encoding="utf-8"), **_inputs())
    assert any("highwire/magnet's gate_dropped" in f and "no recorded decision" in f for f in F)
    gated = sorted(c["id"] for c in M.load()["counters"] if c.get("status") == "sited"
                   and any(it.get("gate_dropped") for it in c["stock"]))
    assert sorted(w.split(": ")[1].split(" ")[0] for w in W if w.startswith("window:")) == gated


# protects the tier ladder: copper sold before badge 1's town, or gold before iron, is named; removing it lets the
# backpack spine run out of order
def test_tiers_out_of_order_are_caught(M):
    def swap(d):
        hw = next(c for c in d["counters"] if c["id"] == "highwire")
        cl = next(c for c in d["counters"] if c["id"] == "cinderlee")
        a, b = _item(d, "highwire", "iron_backpack"), _item(d, "cinderlee", "gold_backpack")
        a["item"], b["item"] = b["item"], a["item"]
    doc = _doc_with(M, swap)
    files, _ = M.build(doc)
    F, _w, _n = MA.audit(doc, MA.load_pack(files), M.overlay_text(doc), **_inputs())
    assert any("gold_backpack first sold at badge 3; the ladder places it at badge 7" in f for f in F)
    assert any("iron_backpack first sold at badge 7; the ladder places it at badge 3" in f for f in F)


# protects the curve band through the whole audit and the floor: Highwire's Iron Backpack (a badge-3 convenience
# line) priced up to $1,000,000 takes badge 3 far above the band whatever the rest of the shelf is, and the fault
# carries the raised ask; a vitamin priced at its sell-back is named
def test_the_curve_and_the_floor_bite(M):
    doc = _doc_with(M, lambda d: _item(d, "highwire", "iron_backpack").update(price=1000000))
    F, _w, _n = MA.audit(doc, MA.load_pack(M.build(doc)[0]), MA.OVERLAY.read_text(encoding="utf-8"), **_inputs())
    b3 = [f for f in F if f.startswith("curve: after badge 3 convenience")]
    assert len(b3) == 1 and int(b3[0].split("convenience ")[1].split(" ")[0]) > 1000000, b3
    doc = _doc_with(M, lambda d: _item(d, "northlight_station", "zinc").update(price=2500))
    F, _w, _n = MA.audit(doc, MA.load_pack(M.build(doc)[0]), MA.OVERLAY.read_text(encoding="utf-8"), **_inputs())
    assert any("northlight_station/zinc sells at $2500 each, not above bank.json's $2500" in f for f in F)


# ------------------------------------------------------------------------- the curve rule and the ladder, real data
def _crit():
    tb = MA.town_badges(MA.read_json(ROOT / "data" / "progression.json"), MA.read_json(ROOT / "data" / "towns.json"))
    return {t: n for t, (n, _f) in tb.items()}


def _real_rule(doc):
    return MA.curve_price_faults(doc, _crit(), MA.trainer_income(doc), MA.read_json(MA.DATA_BANK),
                                 MA.read_json(MA.BLACKOUT))


def _ruled(doc):
    return [(c["id"], it["id"]) for c in doc["counters"] for it in c["stock"] if it.get("price_rule") == "curve_scale"]


# protects the committed convenience strand against price_policies.curve_scale: every critical-path convenience line
# carries the rule and costs what the rule gives. Nonempty: the check reaches ruled lines in the hometown and all
# eight gym towns. Without it a hand-typed price could sit on the curve
def test_the_committed_convenience_prices_are_the_curve_rules(M):
    doc = M.load()
    ruled = _ruled(doc)
    assert len({c for c, _i in ruled}) >= 9                                 # the hometown and the eight gym towns
    assert _real_rule(doc) == []


# protects the curve-rule check's independence from the builder: tools/markets.py's curve_prices MUTATED (data
# untouched) -- its band read 0.01 high, or its earned term $500 a leg richer -- writes prices the audit refuses,
# while the unmutated builder's prices pass. A mutation of the record would move the expectation with the output
@pytest.mark.parametrize("mutation", ["band", "earned"])
def test_a_mutated_curve_rule_generator_is_caught(monkeypatch, M, mutation):
    def priced_by_builder():
        doc = json.loads(json.dumps(M.load()))
        _s, prices = M.curve_prices(doc)
        for c in doc["counters"]:
            for it in c["stock"]:
                if (c["id"], it["id"]) in prices:
                    it["price"] = prices[(c["id"], it["id"])]
        return doc
    assert _real_rule(priced_by_builder()) == []
    if mutation == "band":
        lo_hi = M.curve_band(M.load())
        monkeypatch.setattr(M, "curve_band", lambda doc: (lo_hi[0] + 0.01, lo_hi[1] + 0.01))
    else:
        real = M.r2_earned
        monkeypatch.setattr(M, "r2_earned", lambda doc, effort=None: {
            b: (f, t, e + 500 * b) for b, (f, t, e) in real(doc, effort).items()})
    F = _real_rule(priced_by_builder())
    assert len(F) >= 8 and all("price_policies.curve_scale gives list" in f for f in F), F


# protects the curve-rule check's INPUT PATH: the whole audit, given no effort, reads data/bank.json from disk; pointed
# at a copy with doubled gathering rates, the earned term moves and the committed prices are no longer the rule's.
# Without it the rule's earned term could be a constant
def test_mutation_the_curve_rule_follows_the_bank_file(M, tmp_path, monkeypatch):
    eff = MA.read_json(MA.DATA_BANK)
    for b in eff["buys"]:
        b["rate_per_hour"] *= 2
    (tmp_path / "bank.json").write_text(json.dumps(eff), encoding="utf-8")
    assert not [f for f in _audit(M)[0] if f.startswith("curve rule:")]
    monkeypatch.setattr(MA, "DATA_BANK", tmp_path / "bank.json")
    assert len([f for f in _audit(M)[0] if f.startswith("curve rule:")]) >= 8


# protects TIERED_GOODS' ladder as RELATIVE worth under the curve rule (CURVEPRICE): a ruled line is held to the
# ladder by its list_price, not by the scaled price a player pays -- so a list equal to the ladder raises no finding
# and a list moved off it does, naming the list; and the old ladder price typed back as `price` is not a ladder pass
# but a curve-rule fault. Without it the ruled lines either drown the ladder in findings or escape it entirely
def test_the_ladder_reads_a_ruled_lines_list_price_and_the_rule_reads_its_price(M):
    i = _inputs()
    pack = MA.load_pack(M.build(M.load())[0])
    overlay = MA.OVERLAY.read_text(encoding="utf-8")
    run = lambda d: MA.audit(d, pack, overlay, **i)
    base = M.load()
    ib = _item(base, "highwire", "iron_backpack")
    assert ib["price_rule"] == "curve_scale" and ib["list_price"] == MA.LADDER[SB + "iron_backpack"][1] != ib["price"]
    F, W, _n = run(base)
    assert not [w for w in W if "iron_backpack at highwire" in w]
    assert not [f for f in F if f.startswith("curve rule:")]
    doc = _doc_with(M, lambda d: _item(d, "highwire", "iron_backpack").update(list_price=4600))
    F, W, _n = run(doc)
    assert any("iron_backpack at highwire lists (list_price, curve_scale) at $4600 each; the ladder prices it at $4500"
               in w for w in W), W
    doc = _doc_with(M, lambda d: _item(d, "highwire", "iron_backpack").update(price=4500))
    F, W, _n = run(doc)
    assert not [w for w in W if "iron_backpack at highwire" in w]
    rule = [f for f in F if f.startswith("curve rule:")]
    assert len(rule) == 1 and rule[0].startswith("curve rule: highwire/iron_backpack costs $4500; price_policies."
                                                 "curve_scale gives list $4500 x leg 3's scale ")
    assert rule[0].endswith("= $%d (rounded to $50)" % ib["price"]), rule
    # a line the rule does not price is still held to the ladder by what it costs (Highwire's five Great Balls)
    gb = _item(base, "highwire", "great_ball")
    assert "price_rule" not in gb
    unit = lambda d: _item(d, "highwire", "great_ball")["price"] / gb["count"]
    doc = _doc_with(M, lambda d: _item(d, "highwire", "great_ball").update(price=gb["count"] * 760))
    assert any("great_ball at highwire costs $760 each; the ladder prices it at $750" in w for w in run(doc)[1])
    doc = _doc_with(M, lambda d: _item(d, "highwire", "great_ball").update(price=gb["count"] * 750))
    assert unit(doc) == 750 and not [w for w in run(doc)[1] if "great_ball at highwire" in w]


# ================================================================================================ with the jars
# Never the live server's own mods folder (OVERNIGHT_REVIEW N56: the old default read cobblers-server/mods without the
# coordination lock while the owner's server ran). The fallback is the offline snapshot taken while it was stopped.
JAR_CANDIDATES = [os.environ.get("COBBLERS_JAR_DIR") or "",
                  "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods"]
assert not any(Path(d).resolve() == Path("C:/Users/wnd/Documents/github/cobblers-server/mods").resolve()
               for d in JAR_CANDIDATES[1:]), "the fallback must not be the live server's mods folder"


@pytest.fixture(scope="module")
def jars():
    for d in JAR_CANDIDATES:
        if d and list(Path(d).glob("sophisticatedbackpacks-*.jar")) and list(Path(d).glob("Cobblemon-fabric-*.jar")):
            want = {i for i, on in MA.enabled_items(MA.OVERLAY.read_text(encoding="utf-8")) if not on}
            return MA.JarIndex.from_dir(d, want)
    pytest.skip("NOT_EXECUTED: no folder with the server's jars (set COBBLERS_JAR_DIR)")


# protects A-1 and A-3 on the real jars: every sold id is an item, the three ids TIERED_GOODS 2.6 says do not exist
# really do not, and every switched-off item's recipes carry the condition
def test_ids_and_recipe_conditions_in_the_server_jars(M, jars):
    for missing in ("comforts:sleeping_bag", "cobblecuisine:malasada", "cobblemon:x_defense"):
        assert missing not in jars.items
    assert "cobblemon:x_defence" in jars.items
    # TMCraft's TMs: no lang key, but a model and the tm_moves tag (tmcraft-1.4.19+1.8.0.jar); a TM that does not
    # exist must still fail
    assert "tmcraft:tm_earthquake" not in jars.items and jars.is_item("tmcraft:tm_earthquake")
    assert not jars.is_item("tmcraft:tm_notamove")
    F, _w, _n = _audit(M, index=jars)
    assert [f for f in F if not f.startswith("curve:")] == [], F        # the R2 curve: test_the_committed_shelf_...


# protects the id check against the GENERATOR: an offer of an id that is not in any jar (TIERED_GOODS 2.6's
# 'charcoal', not 'charcoal_stick') must be named
def test_a_generator_giving_a_missing_id_is_caught(monkeypatch, M, jars):
    real = M.merchant_shop
    monkeypatch.setattr(M, "merchant_shop", lambda s: json.loads(json.dumps(real(s)).replace(
        "cobblemon:charcoal_stick", "cobblemon:charcoal")))
    F, _w, _n = _audit(M, index=jars)
    assert "id: cobblemon:charcoal is not an item in any server jar" in F


# ================================================================================================ the keepers, real
# A defect this audit found (2026-10-03): all eleven keepers stood two blocks past the FAR wall of their Mart and ten
# faced away from their plaza. Re-sited the same day on each Mart's door side, facing its plaza (data/markets.json
# counters[].site_why); this now protects the fix
def test_every_keeper_stands_in_front_of_its_mart_clear_of_roads_and_buildings(M):
    F, _w, _n = MA.run(files=M.build(M.load())[0], jar_dir=None)
    assert [f for f in F if f.startswith("keeper")] == [], [f for f in F if f.startswith("keeper")][:4]


# protects the rest of the keeper checks on the real data, apart from the frontage defect above: in no street, lot,
# building, walked line or other NPC's 2-block reach, and R17M places exactly the sited keepers
def test_keepers_are_clear_of_roads_buildings_walked_lines_and_other_npcs(M):
    F, _w, N = MA.run(files=M.build(M.load())[0], jar_dir=None)
    assert [n for n in N if n.startswith("NOT CHECKED: NPCs")] == [], N
    rest = [f for f in F if f.startswith("keeper") and "behind its Mart" not in f and "back to its plaza" not in f]
    assert rest == [], rest
    assert [f for f in F if not f.startswith(("keeper", "curve:"))] == []   # the R2 curve is held strict elsewhere
