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


# protects the curve's source: the income table is read from the ladder document, not retyped
def test_ladder_income_is_read_from_the_document():
    inc = MA.ladder_income()
    assert inc[1] == 9475 and inc[3] == 28655 and inc[8] == 145078 and len(inc) == 8
    with pytest.raises(MA.AuditError):
        MA.ladder_income("### 0.2\n| badge 1 | 1 | 2 | **3** | 4 |\n### 0.3")


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
                towns=MA.read_json(ROOT / "data" / "towns.json"), bank=MA.read_json(MA.BANK), income=MA.ladder_income(),
                base_text=MA.BASE_OVERLAY.read_text(encoding="utf-8"))


def _audit(M, doc=None, overlay_text=None, **kw):
    doc = doc or M.load()
    files, _npcs = M.build(doc)
    i = _inputs()
    return MA.audit(doc, MA.load_pack(files), overlay_text if overlay_text is not None else MA.OVERLAY.read_text(encoding="utf-8"),
                    i["base_text"], i["progression"], i["towns"], i["bank"], i["income"], **kw)


# protects the whole offline contract on the committed data and the pack built from it (jars and keepers aside);
# removing it leaves the markets unaudited between builds
def test_the_built_markets_pass_the_offline_audit(M):
    F, W, N = _audit(M)
    assert F == [], F
    assert any(n.startswith("curve") for n in N)


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


# protects the curve band and the floor: a badge-3 shelf priced up past 0.70, and a vitamin priced at its sell-back,
# are named
def test_the_curve_and_the_floor_bite(M):
    doc = _doc_with(M, lambda d: _item(d, "highwire", "iron_backpack").update(price=9000))
    F, _w, _n = MA.audit(doc, MA.load_pack(M.build(doc)[0]), MA.OVERLAY.read_text(encoding="utf-8"), **_inputs())
    assert any(f.startswith("curve: after badge 3") for f in F)
    doc = _doc_with(M, lambda d: _item(d, "northlight_station", "zinc").update(price=2500))
    F, _w, _n = MA.audit(doc, MA.load_pack(M.build(doc)[0]), MA.OVERLAY.read_text(encoding="utf-8"), **_inputs())
    assert any("northlight_station/zinc sells at $2500 each, not above bank.json's $2500" in f for f in F)


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
    assert F == [], F


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
    assert [f for f in F if not f.startswith("keeper")] == []
