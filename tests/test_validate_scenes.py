"""tools/validate_data.py: the scenes check, conversations with no NPC, and the optional_route trainer class.

Written by the test author, not by the session that wrote tools/scenes_pack.py or data/scenes.json.

Each rule is shown firing on a minimal breaking change to a copy of the real data (data/scenes.json,
data/dialogue.json, data/quests.json, data/progression.json, data/trainers.json read, never written), and the real
data is shown clean. The expected shapes come from the scenes_pack docstring and data/dialogue.json mechanism.notes,
not from earlier validator output.

Not covered, and it needs a running server (EXP-034): that a prop or actor click opens the conversation, that the
beat moves an actor, that a zone's transition fires for the player standing in it. Positions are checked against the
scene's own area only; whether a marker is standable is tests/test_route_events.py and tests/test_route1_mansion.py.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import validate_data as V  # noqa: E402

NAMES = ("scenes.json", "dialogue.json", "quests.json", "progression.json")
REAL = {n: json.loads((ROOT / "data" / n).read_text(encoding="utf-8")) for n in NAMES}


def _ctx(docs):
    rep = V.Report()
    ctx = V.Context(ROOT / "data", None, rep)
    for name, doc in docs.items():
        if doc is not None:
            ctx.files[name] = V.DataFile(Path(name), "data/" + name, json.dumps(doc, indent=2), doc)
    return ctx


def scene_errors(docs):
    ctx = _ctx(docs)
    V.check_scenes(ctx)
    return [f.message for f in ctx.report.findings if f.severity == V.ERROR]


@pytest.fixture
def docs():
    return copy.deepcopy(REAL)


def scene(docs, sid):
    return next(s for s in docs["scenes.json"]["scenes"] if s["id"] == sid)


def conv(docs, cid):
    return next(c for c in docs["dialogue.json"]["conversations"] if c["id"] == cid)


# Without it the whole check could pass on a data set it never read: the real scenes must be seen and be clean.
def test_the_real_scenes_are_clean_and_counted():
    ctx = _ctx(copy.deepcopy(REAL))
    V.check_scenes(ctx)
    errors = [f.message for f in ctx.report.findings if f.severity == V.ERROR]
    assert errors == []
    info = [f.message for f in ctx.report.findings if f.check == "scenes" and f.severity == V.INFO]
    assert info and "checked %d scenes" % len(REAL["scenes.json"]["scenes"]) in info[0]
    assert len(REAL["scenes.json"]["scenes"]) >= 10


# Without it the validator is not wired: `validate_data.py --only scenes` would run nothing.
def test_scenes_check_is_registered():
    assert ("scenes", V.check_scenes) in V.CHECKS
    assert V.SCHEMAS["scenes.json"][0] == "cobblers.scenes/1"


# Without it a scene can point at a quest that does not exist and its beat reads fields nobody writes.
def test_a_scene_whose_quest_does_not_exist_is_an_error(docs):
    scene(docs, "route1_gastly_family")["quest_id"] = "evt_nobody"
    assert any("evt_nobody" in m for m in scene_errors(docs))


# Without it a prop opens a conversation that is not compiled, or another quest's, and the click does nothing or
# advances the wrong quest.
def test_a_prop_conversation_that_is_missing_or_of_another_quest_is_an_error(docs):
    s = scene(docs, "route1_gastly_family")
    s["props"][0]["conversation"] = "dlg_nowhere"
    s["props"][1]["conversation"] = "dlg_route1_picnic_bush"
    errs = scene_errors(docs)
    assert any("dlg_nowhere" in m for m in errs)
    assert any("dlg_route1_picnic_bush" in m and "evt_route1_rattata_picnic" in m for m in errs)


# Without it a clicked conversation also carries an NPC class, and the NPC and the click race for the same cursor.
def test_a_clicked_conversation_with_an_npc_id_is_an_error(docs):
    conv(docs, "dlg_route1_gastly_cup")["npc_id"] = "npc_cup"
    assert any("dlg_route1_gastly_cup" in m and "npc_id null" in m for m in scene_errors(docs))


# Without it R17 places an NPC for a conversation with no NPC class, and spawnnpcat fails on the server.
def test_a_scene_npc_whose_conversation_has_no_npc_id_is_an_error(docs):
    conv(docs, "dlg_route1_rattata_picnic")["npc_id"] = None
    assert any("dlg_route1_rattata_picnic" in m and "no npc_id" in m for m in scene_errors(docs))


# Without it an actor stands outside the area its beat runs in, is never refreshed, and vanishes every cycle.
def test_a_marker_or_slot_outside_the_area_is_an_error(docs):
    s = scene(docs, "route2_rollaway_geodude")
    s["markers"]["geodude_cart"]["at"][0] = s["area"]["to"][0] + 5
    assert any("geodude_cart" in m and "outside the area" in m for m in scene_errors(docs))
    docs2 = copy.deepcopy(REAL)
    s2 = scene(docs2, "route2_rollaway_geodude")
    s2["markers"]["geodude_cart"]["at"][0] = s2["area"]["to"][0]
    s2["markers"]["geodude_cart"]["slots"] = [[0, 0], [1.0, 0]]
    assert any("geodude_cart" in m and "slot" in m for m in scene_errors(docs2))


# Without it an actor's place rule names a marker that is not there and the scene pack refuses to build at prepare.
def test_a_place_rule_naming_an_unknown_marker_is_an_error(docs):
    scene(docs, "route1_gastly_family")["actors"][0]["place"][0]["marker"] = "attic"
    assert any("attic" in m for m in scene_errors(docs))


# Without it a rule placed after an unconditional one is silently dead: the first rule that holds wins.
def test_a_place_rule_after_an_unconditional_one_is_an_error(docs):
    rules = scene(docs, "route1_gastly_family")["actors"][0]["place"]
    rules.insert(0, {"marker": "foyer"})
    assert any("unconditional" in m for m in scene_errors(docs))


# Without it a beat reads a field no quest lists (or nobody declared), which is always unset, so the actor never
# leaves its fallback marker.
def test_a_condition_on_an_undeclared_or_unlisted_field_is_an_error(docs):
    rule = scene(docs, "route1_gastly_family")["actors"][0]["place"][0]
    rule["when"]["field"] = "quest.evt_route1_gastly_family.no_such_field"
    assert any("no_such_field" in m and "does not declare" in m for m in scene_errors(docs))
    docs2 = copy.deepcopy(REAL)
    rule2 = scene(docs2, "route1_gastly_family")["actors"][0]["place"][0]
    rule2["when"]["field"] = "quest.evt_route1_rattata_picnic.berry_left"
    assert any("berry_left" in m and "does not list" in m for m in scene_errors(docs2))


# Without it a misspelt checkpoint value ('libary') compiles to a comparison that never holds.
def test_a_condition_value_outside_the_enum_or_of_the_wrong_type_is_an_error(docs):
    rules = scene(docs, "route1_gastly_family")["actors"][0]["place"]
    enum_rule = next(r for r in rules if r.get("when", {}).get("field", "").endswith(".checkpoint"))
    enum_rule["when"]["value"] = "libary"
    bool_rule = next(r for r in rules if r.get("when", {}).get("field", "").endswith(".completed"))
    bool_rule["when"]["value"] = "yes"
    errs = scene_errors(docs)
    assert any("'libary'" in m for m in errs)
    assert any("boolean" in m and "'yes'" in m for m in errs)


# Without it a zone runs a transition that checks or moves items, which a beat cannot do (the probe is read before
# its queued command runs) and only a dialogue may.
def test_a_zone_transition_that_checks_or_moves_items_is_an_error(docs):
    s = scene(docs, "route1_gastly_family")
    tid = s["zones"][0]["transitions"][0]
    q = next(q for q in docs["quests.json"]["quests"] if q["id"] == s["quest_id"])
    t = next(t for t in q["transitions"] if t["id"] == tid)
    t["conditions"].append({"kind": "not", "condition": {"kind": "held_item", "item": "minecraft:stick"}})
    t["effects"].append({"kind": "give_item", "item": "minecraft:stick", "count": 1})
    errs = scene_errors(docs)
    assert any("checks an item" in m for m in errs)
    assert any("moves items" in m for m in errs)


# Without it a zone names a transition the quest does not have and the zone does nothing.
def test_a_zone_naming_an_unknown_transition_is_an_error(docs):
    scene(docs, "route1_gastly_family")["zones"][0]["transitions"] = ["reach_nowhere"]
    assert any("reach_nowhere" in m for m in scene_errors(docs))


# Without it a dialogue's sync_scene or scene_function names a scene or function that is not there: the command runs
# and does nothing, and the Nosepass pulse or the Wooper encounter never happens.
def test_a_quest_effect_naming_an_unknown_scene_or_function_is_an_error(docs):
    def effects(quest_id, kind):
        q = next(q for q in docs["quests.json"]["quests"] if q["id"] == quest_id)
        return [e for t in q["transitions"] for e in t.get("effects") or [] if e.get("kind") == kind]
    effects("evt_route3_nosepass_signs", "scene_function")[0]["function"] = "no_pulse"
    effects("evt_route1_gastly_family", "sync_scene")[0]["scene"] = "route1_rattata_picnic"
    errs = scene_errors(docs)
    assert any("no_pulse" in m for m in errs)
    assert any("route1_rattata_picnic" in m and "belongs to quest" in m for m in errs)


# Without it a conversation with npc_id null that no prop or actor opens ships and can never be reached.
def test_an_npc_less_conversation_nothing_opens_is_an_error(docs):
    s = scene(docs, "viltri_north_bank")
    s["props"] = []
    assert any("dlg_viltri_north_bank" in m and "opens it" in m for m in scene_errors(docs))


# Without it the orphan rule could not fire when data/scenes.json is missing altogether.
def test_without_scenes_every_npc_less_conversation_is_an_orphan(docs):
    docs["scenes.json"] = None
    errs = scene_errors(docs)
    nulls = [c["id"] for c in REAL["dialogue.json"]["conversations"] if "npc_id" in c and c["npc_id"] is None]
    assert nulls
    for cid in nulls:
        assert any(cid in m for m in errs)


# ------------------------------------------------------------------ schema: npc_id and trainer class

def _schema_errors(tmp_path, dialogue=None, trainers=None):
    (tmp_path / "world.json").write_text(json.dumps({"schema": "cobblers.world/1"}), encoding="utf-8")
    if dialogue is not None:
        (tmp_path / "dialogue.json").write_text(json.dumps(dialogue), encoding="utf-8")
    if trainers is not None:
        (tmp_path / "trainers.json").write_text(json.dumps(trainers), encoding="utf-8")
    rep = V.Report()
    V.check_schema(V.Context(tmp_path, None, rep))
    return [f.message for f in rep.findings if f.severity == V.ERROR]


def _conv(**kw):
    c = {"id": "dlg_x", "quest_id": "q", "npc_id": "npc_x", "scope": "player", "cursor": {}, "entry_rules": [],
         "nodes": []}
    c.update(kw)
    return c


# Without it every prop and actor conversation (npc_id null by design) is reported missing a required field, and the
# report is 50 errors of noise that hides a real one.
def test_npc_id_may_be_null_but_not_absent(tmp_path):
    ok = {"schema": "cobblers.dialogue/1", "conversations": [_conv(npc_id=None)]}
    assert _schema_errors(tmp_path, dialogue=ok) == []
    gone = _conv()
    del gone["npc_id"]
    bad = {"schema": "cobblers.dialogue/1", "conversations": [gone]}
    assert any('"npc_id"' in m for m in _schema_errors(tmp_path, dialogue=bad))


# Without it null would also pass for fields that are not allowed to be null.
def test_null_is_still_missing_for_other_required_fields(tmp_path):
    bad = {"schema": "cobblers.dialogue/1", "conversations": [_conv(quest_id=None)]}
    assert any('"quest_id"' in m for m in _schema_errors(tmp_path, dialogue=bad))


# Without it the Lake Viltri north-bank angler (class optional_route) is a schema error, while a class nobody defined
# must still be one.
def test_optional_route_is_an_allowed_trainer_class_and_others_are_not(tmp_path):
    def doc(cls):
        return {"schema": "cobblers.trainers/1",
                "trainers": [{"id": "t", "display_name": "T", "class": cls, "team": []}]}
    assert _schema_errors(tmp_path, trainers=doc("optional_route")) == []
    assert any("class" in m for m in _schema_errors(tmp_path, trainers=doc("side_route")))
