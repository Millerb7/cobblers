"""Oak gives the starter (the owner's priority zero, 2026-10-05): the starter config, Oak's conversation and the
compiler's open_starter_screen construct, as generated from the real data.

Written in the same session as the construct (the unit's own tests, not its independent audit).

What is asserted: the shared starter config locks the native screen on join and offers exactly the five forms
data/mythical_starters.json records; Oak's offer runs Cobblemon's `openstarterscreen` for the talking player and
reads its result from a score preset to -1, so only a 0 that the command itself returned marks a player as having
chosen; no compiled conversation gives a Pokemon; the starter_chosen callback ships once and adds the same tag the
conversation reads; and in Oak's conversation no node that sends the player off (record_oak_sendoff) is reachable
from the initial node without passing a starter-gated edge.

Not covered, and it needs a running server: that the callback fires (EXP to run on staging), that the client keeps
the starter screen when the dialogue close arrives after it, and that a locked player's own key is refused.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import mythical_starters as MS  # noqa: E402

DATA = ROOT / "data"
CONV_ID = "dlg_main_pallet_oak"
STARTERS = ROOT / "modpack" / "config" / "cobblemon" / "starters.json"


def _json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def conv():
    return next(c for c in _json(DATA / "dialogue.json")["conversations"] if c["id"] == CONV_ID)


@pytest.fixture(scope="module")
def compiled():
    files = CD.build(CONV_ID, DATA)
    doc = files["data/cobblers/dialogues/%s.json" % CONV_ID]
    return files, doc, {p["id"]: p for p in doc["pages"]}


def _option(pages, node, value):
    return next(o for o in pages[node]["input"]["options"] if o["value"] == value)


# Without it the chooser opens as a menu on join instead of in Oak's lab (the owner, 2026-10-06: "Oak offering the
# starters in the lab as a scene rather than a menu on join"; true from 2026-10-05 to 2026-10-06): Cobblemon sets a new
# player's starterLocked to !allowStarterOnJoin (PlayerDataJsonBackend @1.8.0), and Oak's offer unlocks it.
def test_the_config_locks_the_chooser_on_join_and_offers_exactly_the_five():
    cfg = _json(STARTERS)
    assert cfg["allowStarterOnJoin"] is False
    # with no datapack `starters` category the screen shows this list (getStarterList falls back to the config)
    assert [c["name"] for c in cfg["starters"]] == ["cobblers_mythical"]
    assert cfg["starters"][0]["pokemon"] == MS.config_entries(_json(DATA / "mythical_starters.json"))
    assert len(cfg["starters"][0]["pokemon"]) == 8


# Without it the option opens a screen for the wrong player, or a command that never ran reads as "already chose".
def test_the_offer_runs_openstarterscreen_for_the_talking_player_with_a_preset_score(compiled):
    _files, _doc, pages = compiled
    act = _option(pages, "oak_offer_002", "oak_offer_choose")["action"]
    preset = "'execute as ' + q.player.uuid + ' run scoreboard players set @s %s -1'" % CD.STARTER_SCORE
    opened = ("'execute as ' + q.player.uuid + ' store result score @s %s run openstarterscreen @s'"
              % CD.STARTER_SCORE)
    tagged = ("'execute as ' + q.player.uuid + ' if score @s %s matches 0 run tag @s add %s'"
              % (CD.STARTER_SCORE, CD.STARTER_TAG))
    made = "'scoreboard objectives add %s dummy'" % CD.STARTER_SCORE
    for part in (made, preset, opened, tagged):
        assert part in act, part
    assert act.index(made) < act.index(preset) < act.index(opened) < act.index(tagged)
    assert act.count("openstarterscreen") == 1


# Without it a player who already chose is sent the screen again (a no-op, and Oak never moves on), or a player who
# was just sent the screen is shown the send-off before choosing.
def test_a_player_who_has_chosen_goes_on_and_anyone_else_keeps_the_screen(compiled):
    _files, _doc, pages = compiled
    act = _option(pages, "oak_offer_002", "oak_offer_choose")["action"]
    branch = act[act.index("q.player.has_tag('%s') ?" % CD.STARTER_TAG):]
    chosen, _, other = branch.partition(" : ")
    # a player who has chosen goes on to Oak's League rules (2026-10-06), then the send-off
    assert "q.dialogue.set_page('oak_mode_001')" in chosen
    assert "= 'oak_mode_001'" in chosen
    assert "q.dialogue.close()" in other and "set_page" not in other


# Without it two starters are possible: the only grant is Cobblemon's own screen, which refuses a second pick.
def test_no_compiled_conversation_gives_a_pokemon():
    files, _done, _refused = CD.build_all(DATA)
    for rel, content in files.items():
        text = content if isinstance(content, str) else json.dumps(content)
        for cmd in ("givepokemon", "pokegive", "spawnpokemon"):
            assert cmd not in text, (rel, cmd)


# Without it Oak cannot tell, on the next talk, that the pick was made, or two conversations write the callback.
def test_the_callback_ships_once_and_adds_the_tag_the_conversation_reads(compiled):
    files, _done, _refused = CD.build_all(DATA)
    cbs = [k for k in files if "/callbacks/" in k]
    assert CD.STARTER_CALLBACK in cbs
    assert CD.STARTER_CALLBACK.startswith("data/cobblemon/callbacks/starter_chosen/")
    assert "add %s'" % CD.STARTER_TAG in files[CD.STARTER_CALLBACK]
    _f, doc, _p = compiled
    assert "q.player.has_tag('%s')" % CD.STARTER_TAG in doc["initializationAction"]


# Without it an untouched player lands on a node the conversation no longer starts at.
def test_the_progression_initial_is_the_conversations_initial(conv):
    fields = {f["id"]: f for f in _json(DATA / "progression.json")["quest_fields"]}
    assert fields[conv["cursor"]["progression_field"]]["initial"] == conv["cursor"]["initial_node"] == "oak_offer_001"


def _ungated_reach(conv):
    """Nodes reachable from the initial node through edges that do not need a starter: line `next`, and every choice
    response except open_starter_screen's. Entry rules other than `$cursor` count only when they read no starter."""
    nodes = {n["id"]: n for n in conv["nodes"]}
    start = [conv["cursor"]["initial_node"]]
    for rule in conv["entry_rules"]:
        if rule["node"] != "$cursor" and "starter_chosen" not in json.dumps(rule["when"]):
            start.append(rule["node"])
    seen, todo = set(), list(start)
    while todo:
        nid = todo.pop()
        if nid in seen or nid not in nodes:
            continue
        seen.add(nid)
        n = nodes[nid]
        if n["kind"] == "line":
            todo.append(n["next"])
        else:
            for r in n["responses"]:
                if any(a["kind"] == "open_starter_screen" for a in r.get("actions") or []):
                    continue
                for a in r.get("actions") or []:
                    if a["kind"] == "set_cursor":
                        todo.append(a["node"])
                if r.get("next"):
                    todo.append(r["next"])
    return seen


def _sendoff_nodes(conv):
    return {n["id"] for n in conv["nodes"]
            if any(a.get("transition") == "record_oak_sendoff" for a in n.get("actions_after_acknowledge") or [])}


# Without it a player walks out of Pallet with an empty party: the send-off unlocks Mina and the rest of the quest.
def test_no_path_reaches_the_send_off_without_a_starter(conv):
    assert _sendoff_nodes(conv)
    assert not _ungated_reach(conv) & _sendoff_nodes(conv)
    # and nothing else can move Oak's cursor before the send-off: every transition that writes it needs a later stage
    # -- or is run only from a page that is itself behind the starter gate (Oak's League rules, 2026-10-06: the two
    # record_trainer_mode_* transitions move the cursor to their "recorded" line, and are reachable only after the pick)
    quest = next(q for q in _json(DATA / "quests.json")["quests"] if q["id"] == conv["quest_id"])
    ungated = _ungated_reach(conv)
    used_from = {}
    for n in conv["nodes"]:
        for r in n.get("responses") or []:
            for a in r.get("actions") or []:
                if a["kind"] == "quest_transition":
                    used_from.setdefault(a["transition"], set()).add(n["id"])
        for a in n.get("actions_after_acknowledge") or []:
            if a["kind"] == "quest_transition":
                used_from.setdefault(a["transition"], set()).add(n["id"])
    for t in quest["transitions"]:
        if any(e.get("field") == conv["cursor"]["progression_field"] for e in t["effects"]):
            stages = [c.get("value") for c in t["conditions"] if c.get("field") == "quest.main_worldshift_reveal.stage"]
            gated = t["id"] in used_from and not (used_from[t["id"]] & ungated)
            assert (stages and "not_started" not in stages) or gated, t["id"]


# The check above bites: an ungated way to oak_001 is found.
def test_harness_an_ungated_edge_to_the_send_off_is_caught(conv):
    bad = copy.deepcopy(conv)
    node = next(n for n in bad["nodes"] if n["id"] == "oak_offer_002")
    wait = next(r for r in node["responses"] if r["id"] == "oak_offer_wait")
    wait["actions"], wait["next"] = [], "oak_001"
    assert _ungated_reach(bad) & _sendoff_nodes(bad)


def _compiler(conv):
    quests = {q["id"]: q for q in _json(DATA / "quests.json")["quests"]}
    fields = {f["id"]: f for f in _json(DATA / "progression.json")["quest_fields"]}
    return conv, quests, fields


# Without it a response mixes the screen with a transition or a close the construct does not order.
def test_open_starter_screen_is_a_responses_only_action_and_needs_a_next(conv):
    for mutate in ("extra_action", "no_next"):
        bad = copy.deepcopy(conv)
        r = next(r for n in bad["nodes"] if n["id"] == "oak_offer_002" for r in n["responses"]
                 if r["id"] == "oak_offer_choose")
        if mutate == "extra_action":
            r["actions"].append({"kind": "close_dialogue"})
        else:
            del r["next"]
        with pytest.raises(CD.Unsupported):
            CD.compile_conversation(*_compiler(bad))


def test_the_starter_chosen_condition_reads_the_tag():
    c = CD.Compiler({"nodes": [], "cursor": {"progression_field": "x", "initial_node": "a"}, "entry_rules": []},
                    {"transitions": []}, {})
    assert c.cond({"kind": "starter_chosen"}, {}) == "q.player.has_tag('%s')" % CD.STARTER_TAG
