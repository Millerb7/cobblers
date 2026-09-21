"""The trader re-application function puts exactly one trader on each stall, however often it runs.

Each property below was a failure on the disposable world on 2026-09-21 (tools/traders.py docstring):
killing two ticks after force-loading missed the saved traders and stacked another per run; one town's pass
stripping every "new" tag stopped the next town de-duplicating; merchants with AI walked up to 40 blocks off
their stalls. Offline: a fake template stands in for the installed pack.

Written by the same session that wrote tools/traders.py; not independently reviewed (docs/HANDOVER_CODEX.md).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import traders as TR  # noqa: E402

KIND = "cobbledollars:cobble_merchant"


def fake_entity(template):
    return KIND, {"CustomName": '"%s Seller"' % template.split("/")[-1], "Offers": {"Recipes": []},
                  "UUID": [1, 2, 3, 4], "Pos": [0.0, 0.0, 0.0], "Tags": ["from_template"]}


def rec(i, town="t1", x=0, y=100, z=0):
    return {"id": "%s_vendor_%02d" % (town, i), "settlement": town, "template": "bca:shop/s%d" % i,
            "source": {}, "position": {"x": x + 5 * i, "y": y, "z": z}, "status": "planned"}


def functions(town="t1", n=3):
    fake = lambda t: (KIND, {k: v for k, v in fake_entity(t)[1].items() if k not in TR.ENGINE_OWNED})
    return TR.town_functions(town, [rec(i, town) for i in range(1, n + 1)], fake)


def ticks(line):
    return int(re.search(r" (\d+)t replace$", line).group(1))


def test_saved_traders_have_time_to_load_before_the_kill():
    # at 2 ticks the kill missed the saved trader; at 20 it found it
    f = functions()
    loader = f["vendors_t1"]
    assert loader[2].startswith("forceload add ")
    assert ticks(loader[-1]) >= 20
    assert ticks(f["vendors_t1_place"][-1]) >= 20


def test_summons_carry_the_new_tag_and_stand_still():
    for line in functions()["vendors_t1_place"]:
        if line.startswith("summon "):
            assert "NoAI:1b" in line and "PersistenceRequired:1b" in line
            assert '"%s"' % TR.TAG_NEW in line and '"%s"' % TR.TAG_ALL in line
            assert "UUID" not in line and "Pos:" not in line and "from_template" not in line


def test_old_copies_die_only_where_the_new_one_stands():
    done = functions()["vendors_t1_done"]
    kills = [l for l in done if " run kill " in l]
    assert kills and all(l.startswith("execute if entity @e[tag=cobblers_vendor_t1_vendor_") for l in kills)
    assert all(",tag=%s]" % TR.TAG_NEW in l.split(" run ")[0] for l in kills)


def test_one_towns_pass_leaves_other_towns_new_tags_alone():
    for line in functions()["vendors_t1_done"]:
        if line.startswith("tag "):
            assert re.match(r"tag @e\[tag=cobblers_vendor_t1_vendor_\d+,tag=%s\] remove %s$" % (TR.TAG_NEW, TR.TAG_NEW), line)


def test_strays_are_matched_by_type_and_name_never_everything():
    for line in functions()["vendors_t1_done"]:
        if "kill @e[type=" in line:
            sel = line.split("kill @e[")[1]
            assert "type=%s" % KIND in sel and 'name="' in sel and "tag=!%s" % TR.TAG_ALL in sel


def test_the_plaza_is_released_last_and_nothing_is_released_early():
    f = functions()
    assert not any(l.startswith("forceload remove") for l in f["vendors_t1_place"])
    assert f["vendors_t1_done"][-1].startswith("forceload remove ")


def test_the_manifest_passes_its_static_rules():
    doc = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    assert TR.static_problems(doc, placements, ROOT / "derived" / "towns") == []
    assert not [p for p in placements["placements"] if p.get("kind") == "vendor"], "traders live in data/traders.json"


def test_static_rules_catch_the_mistakes():
    doc = {"traders": [rec(1), dict(rec(1)), dict(rec(2), id="Bad Id"), dict(rec(3), position={"x": 5, "y": 100, "z": 0}),
                       dict(rec(4), status="done"), dict(rec(5), settlement="nowhere")]}
    placements = {"settlements": [{"id": "t1"}]}
    msgs = [m for _, m in TR.static_problems(doc, placements)]
    assert "duplicate id" in msgs
    assert any("entity tag" in m for m in msgs)
    assert any("same block" in m for m in msgs)
    assert any("status must be" in m for m in msgs)
    assert any("not a settlement" in m for m in msgs)


def test_counts_become_problems():
    p = dict(TR.problems_from_counts({"a": (0, 0, 0), "b": (2, 1, 0), "c": (1, 0, None), "d": (1, 1, 2), "e": (1, 1, 0)}))
    assert set(p) == {"a", "b", "c", "d"}
