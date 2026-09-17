"""tools/compile_dialogue.py on the real thirsty-stranger data: the runtime rules EXP-022 found are compiled in.

Written in the same session as the compiler (not independently authored; see docs/HANDOVER_CODEX.md).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402

CONV = "dlg_route1_thirsty_stranger"


@pytest.fixture(scope="module")
def compiled():
    files = CD.build(CONV, ROOT / "data", place=(1402, 125, 4794))
    return files, files["data/cobblers/dialogues/%s.json" % CONV]


def pages(doc):
    return {p["id"]: p for p in doc["pages"]}


# Every authored node must become a page, or a stored cursor can point at a page that does not exist.
def test_every_node_is_a_page_and_every_set_page_target_exists(compiled):
    _, doc = compiled
    conv = next(c for c in json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))["conversations"] if c["id"] == CONV)
    assert set(pages(doc)) == {n["id"] for n in conv["nodes"]}
    text = json.dumps(doc)
    import re
    for target in re.findall(r"set_page\('([^']+)'\)", text):
        assert target in pages(doc)


# EXP-022: `give <uuid>` is refused as an entity selector; the first run lost every reward item to it.
def test_gives_run_as_the_player_never_with_a_uuid_target(compiled):
    text = json.dumps(compiled[1])
    assert "'give ' + q.player.uuid" not in text
    assert "run give @s cobblemon:black_glasses 1" in text


# EXP-022: storing into a missing objective fails silently; a returned glass bottle was lost that way.
def test_every_give_creates_the_objective_before_storing_into_it(compiled):
    for page in compiled[1]["pages"]:
        actions = [page["input"]] if isinstance(page["input"], str) else [o["action"] for o in page["input"]["options"]]
        for a in actions:
            for i in range(a.count("store success score")):
                at = [j for j in range(len(a)) if a.startswith("store success score", j)][i]
                assert "scoreboard objectives add cobblers_tx dummy" in a[:at]


# The claim flag must depend on delivery; the first run marked the reward claimed although nothing was given.
def test_reward_claim_is_written_only_when_no_give_failed(compiled):
    ta08 = pages(compiled[1])["ta08"]["input"]
    claim = "t.d.cobblers__quest__evt_route1_thirsty_stranger__reward_claimed = 1;"
    guard = "q.player.has_tag('cobblers_give_failed') ? { v.cobblers_retry = 1; } : { %s }" % claim
    assert guard in ta08
    assert ta08.count(claim) == 1


# q.player.run_command runs with the player's permission and fails for non-operators.
def test_commands_are_server_sourced(compiled):
    assert "q.player.run_command" not in json.dumps(compiled[1])


# The strict predicate is what refuses other potions; Molang is_of cannot.
def test_bottle_option_uses_the_strict_water_predicate(compiled):
    offer = pages(compiled[1])["offer_water"]["input"]["options"]
    bottle = next(o for o in offer if o["value"] == "offer_bottle")
    assert 'minecraft:potion[potion_contents={potion:"minecraft:water"}]' in bottle["action"]
    assert "is_of('minecraft:potion')" not in json.dumps(compiled[1])


# Functions are parsed before NPC classes load, so a placement function fails; the command is emitted as text.
def test_placement_is_a_command_not_a_function(compiled):
    files, _ = compiled
    assert files["placement.txt"] == "spawnnpcat 1402 125 4794 cobblers:npc_route1_thirsty_stranger\n"
    assert not any("/function/" in k for k in files)


# Anything the compiler does not know stops compilation instead of emitting a guess.
def test_unknown_condition_kind_is_refused():
    c = CD.Compiler({"nodes": [], "cursor": {"progression_field": "x", "initial_node": "a"}, "entry_rules": []},
                    {"transitions": []}, {})
    with pytest.raises(CD.Unsupported):
        c.cond({"kind": "moon_phase"}, {})
