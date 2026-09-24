"""tools/compile_dialogue.py beyond the thirsty stranger: --all, conversations with no NPC, speakers, enum initial
values, and the two effects that reach the scene runtime (sync_scene, scene_function).

Written by the test author, not by the session that extended the compiler.

What is asserted, on the real data (data/dialogue.json, data/quests.json, data/progression.json, data/scenes.json):
build_all compiles every conversation except the ones it lists with a reason, and today that is exactly the two
crushed-house conversations for their world-scoped field; a conversation with npc_id null has no NPC class, one with
an npc_id has exactly one, naming its own dialogue; every conversation a scene opens (prop, actor or NPC) is in the
pack; a speaker mapped to null is narration (its page has no speaker); an enum's declared initial value also matches
the unset key 0 and no other value does; sync_scene and scene_function compile to server-sourced commands whose
function paths exist in the scene pack, and an id that is not [a-z0-9_]+ is refused.

Not covered, and it needs a running server (EXP-034): that /opendialogue opens a page for the clicker, that a
narration page renders with no speaker, that the queued `function cobblers:scenes/<id>/beat` runs as that player.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import scenes_pack as SP  # noqa: E402

DATA = ROOT / "data"
DIALOGUE = json.loads((DATA / "dialogue.json").read_text(encoding="utf-8"))
SCENES = json.loads((DATA / "scenes.json").read_text(encoding="utf-8"))
PROG = json.loads((DATA / "progression.json").read_text(encoding="utf-8"))
CONVS = {c["id"]: c for c in DIALOGUE["conversations"]}


@pytest.fixture(scope="module")
def built():
    return CD.build_all(DATA)


def dlg_path(cid):
    return "data/cobblers/dialogues/%s.json" % cid


# Without it a conversation is dropped from the pack with no reason given, and its NPC or prop opens nothing.
def test_every_conversation_is_compiled_or_refused_with_a_reason(built):
    files, done, refused = built
    assert set(done) | set(refused) == set(CONVS)
    assert not set(done) & set(refused)
    assert all(str(why).strip() for why in refused.values())
    for cid in done:
        assert dlg_path(cid) in files


# Without it a new refusal (a conversation that silently stops shipping) passes unnoticed; today only the crushed
# house is refused, for its shared world-scoped house state.
def test_only_the_crushed_house_conversations_are_refused_and_for_world_scope(built):
    _files, _done, refused = built
    assert set(refused) == {"dlg_pallet_crushed_house_hank", "dlg_pallet_crushed_house_lena"}
    assert all("world-scoped" in why for why in refused.values())


# Without it a prop's or actor's conversation gets an NPC class, and a stray NPC could be spawned for it; or an NPC's
# conversation loses its class and spawnnpcat has nothing to place.
def test_npc_classes_exist_exactly_for_conversations_with_an_npc_id(built):
    files, done, _refused = built
    npc_files = {k for k in files if k.startswith("data/cobblers/npcs/")}
    want = {"data/cobblers/npcs/%s.json" % CONVS[c]["npc_id"] for c in done if CONVS[c].get("npc_id")}
    assert npc_files == want
    for c in done:
        npc = CONVS[c].get("npc_id")
        if npc:
            cls = files["data/cobblers/npcs/%s.json" % npc]
            assert cls["interaction"] == {"type": "dialogue", "dialogue": "cobblers:%s" % c}


# Without it the null-npc path is never exercised: the data must hold prop/actor conversations.
def test_the_data_has_npc_less_conversations_and_they_compile(built):
    _files, done, _refused = built
    nulls = [c for c in CONVS.values() if "npc_id" in c and c["npc_id"] is None]
    assert len(nulls) >= 10
    assert all(c["id"] in done for c in nulls)


# Without it a scene's prop, actor or NPC opens a dialogue that is not in cobblers_dialogue, and the click or the
# NPC's interaction fails on the server.
def test_every_conversation_a_scene_opens_is_in_the_pack(built):
    files, _done, _refused = built
    opened = set()
    for s in SCENES["scenes"]:
        opened |= {p["conversation"] for p in s.get("props") or []}
        opened |= {a["conversation"] for a in s.get("actors") or []}
        opened |= {n["conversation"] for n in s.get("npcs") or []}
    assert opened
    missing = sorted(c for c in opened if dlg_path(c) not in files)
    assert missing == []
    npcs = {CONVS[n["conversation"]]["npc_id"] for s in SCENES["scenes"] for n in s.get("npcs") or []}
    assert all("data/cobblers/npcs/%s.json" % n in files for n in npcs)


# Without it `--place` would write a spawnnpcat for a class that does not exist.
def test_placing_an_npc_less_conversation_is_refused():
    cid = next(c["id"] for c in CONVS.values() if "npc_id" in c and c["npc_id"] is None)
    with pytest.raises(SystemExit):
        CD.build(cid, DATA, place=(0, 64, 0))


# Without it a narration line is shown as spoken by someone called "Narration".
def test_a_speaker_mapped_to_null_is_narration_with_no_speaker(built):
    files, _done, _refused = built
    checked = 0
    for c in CONVS.values():
        names = c.get("speakers")
        if not isinstance(names, dict) or dlg_path(c["id"]) not in files:
            continue
        doc = files[dlg_path(c["id"])]
        pages = {p["id"]: p for p in doc["pages"]}
        for n in c["nodes"]:
            sid = n.get("speaker")
            if not sid or sid not in names:
                continue
            if names[sid] is None:
                assert "speaker" not in pages[n["id"]], (c["id"], n["id"])
                assert sid not in doc["speakers"]
                checked += 1
            else:
                assert pages[n["id"]]["speaker"] == sid
                assert doc["speakers"][sid]["name"] == names[sid]
    assert checked > 0, "no narration page in the data: the rule was never exercised"


def _enum_field():
    f = next(f for f in PROG["quest_fields"] if f["id"] == "quest.evt_route1_gastly_family.checkpoint")
    assert f["type"] == "enum" and f["initial"] == "foyer"
    return f


def _compiler(field):
    quest = {"id": field["quest_id"], "transitions": [], "progression_field_refs": [field["id"]]}
    conv = {"nodes": [], "cursor": {"progression_field": None, "initial_node": None}, "entry_rules": []}
    return CD.Compiler(conv, quest, {field["id"]: field})


# Without it a player who has never touched the quest (the key unset, 0) does not match its initial state, and an
# actor placed "at the foyer unless..." or a check on the initial checkpoint never fires for a new player.
def test_an_enum_initial_value_also_matches_the_unset_key():
    f = _enum_field()
    c = _compiler(f)
    key = "t.d.cobblers__" + f["id"].replace(".", "__")
    got = c.cond({"kind": "progression_equals", "field": f["id"], "value": "foyer"}, {})
    assert "%s == 'foyer'" % key in got and "%s == 0" % key in got
    other = c.cond({"kind": "progression_equals", "field": f["id"], "value": "library"}, {})
    assert "== 0" not in other


# Without it the dialogue's click leaves the actor where it was until the next cycle, or runs a function path built
# from unchecked text; and the command must be the server's, not the player's (non-operators cannot run functions).
@pytest.mark.parametrize("effect,fn", [
    ({"kind": "sync_scene", "scene": "route1_gastly_family"}, "cobblers:scenes/route1_gastly_family/beat"),
    ({"kind": "scene_function", "scene": "route3_nosepass_signs", "function": "pulse"},
     "cobblers:scenes/route3_nosepass_signs/fn/pulse"),
])
def test_scene_effects_compile_to_a_server_command_running_the_scene_function_as_the_player(effect, fn):
    c = _compiler(_enum_field())
    got = c.effect(effect)
    assert "q.run_command('execute as ' + q.player.uuid + ' at @s run function %s')" % fn in got
    assert "q.player.run_command" not in got


# Without it an id with a slash or capitals becomes part of a function path and points anywhere.
@pytest.mark.parametrize("effect", [
    {"kind": "sync_scene", "scene": "../route1"},
    {"kind": "sync_scene", "scene": "Route1"},
    {"kind": "scene_function", "scene": "route3_nosepass_signs", "function": "pulse/../x"},
])
def test_scene_effect_ids_must_be_plain(effect):
    with pytest.raises(CD.Unsupported):
        _compiler(_enum_field()).effect(effect)


# Without it a dialogue compiles a call to a scene function the scene pack does not write, and it does nothing.
def test_every_scene_function_a_dialogue_runs_exists_in_the_scene_pack(built):
    files, _done, _refused = built
    scene_files, _scenes = SP.build(DATA)
    text = json.dumps(files)
    calls = set(re.findall(r"run function (cobblers:scenes/[a-z0-9_/]+)", text))
    assert calls, "no dialogue reaches the scene runtime: the rule was never exercised"
    have = {"cobblers:" + k[len("data/cobblers/function/"):-len(".mcfunction")]
            for k in scene_files if k.endswith(".mcfunction")}
    assert sorted(calls - have) == []
