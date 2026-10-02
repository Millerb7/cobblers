"""rift_crisis_resolved: the Rift finale's flag has exactly one setter, and the setter is emitted.

The chain, each link read from its own file rather than from the generator that emits the next:

  data/progression.json   flags[rift_crisis_resolved].set_by = quest_transition (quest, transition, invoked_by)
  data/quests.json        that transition's effects call cobblers:flag/rift_crisis_resolved/grant, and NO other
                          transition, effect or record anywhere in data/ names that function
  tools/progression_pack  emits the grant function, whose one command grants exactly that advancement, and the
                          advancement's only criterion is minecraft:impossible (nothing but the function sets it)
  data/dialogue.json      the conversations that invoke the transition are exactly set_by.invoked_by (none today:
                          Hoopa's release actor waits on the cradle chamber), so the record and the data move together

Not covered: that the transition fires in game (nothing invokes it yet), that `advancement grant` from a compiled
dialogue's run_command reaches the player (the same construct as the relic HQ guard's hq_admit, itself unobserved),
and Codex's multiplayer "one release advances every eligible player" (not built; per player like every flag).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import progression_pack as PP  # noqa: E402

DATA = ROOT / "data"
FLAG = "rift_crisis_resolved"
ADV = "cobblers:flag/%s" % FLAG
GRANT = "cobblers:flag/%s/grant" % FLAG


def _json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _flag():
    hits = [f for f in _json("progression.json")["flags"] if f.get("id") == FLAG]
    assert len(hits) == 1, "%s must be declared exactly once in data/progression.json flags[]" % FLAG
    return hits[0]


def _transitions():
    out = []
    for q in _json("quests.json")["quests"]:
        for t in q.get("transitions") or []:
            out.append((q["id"], t))
    return out


def _walk(node):
    """Every dict anywhere in a JSON value."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _real_pack():
    placements = _json("placements.json")
    return PP.files(PP.plan(PP.load(DATA / "progression.json"), placements=placements))


def test_flag_is_declared_with_a_quest_transition_setter():
    set_by = _flag()["set_by"]
    assert set_by["kind"] == "quest_transition"
    assert set_by["quest"] == "main_worldshift_reveal"
    assert set_by["transition"] == "unlock_league_after_rift_resolution"


def test_the_league_chapter_requires_the_flag():
    # ARC.md's League row: 'Requires rift_crisis_resolved'. The chapter ledger is data, not a runtime gate.
    league = next(c for c in _json("progression.json")["chapters"] if c["id"] == "league")
    assert FLAG in league["unlocked_by"] and "gym8_cleared" in league["unlocked_by"]


def test_exactly_one_transition_grants_the_flag_and_it_is_the_declared_one():
    set_by = _flag()["set_by"]
    granting = [(qid, t["id"]) for qid, t in _transitions()
                if any(e.get("kind") == "function" and e.get("function") == GRANT for e in t.get("effects") or [])]
    assert granting == [(set_by["quest"], set_by["transition"])]


def test_the_grant_is_the_transitions_first_effect_and_it_moves_the_stage_to_rift_released():
    # 'Invoke only after the authoritative setter commits': the grant runs before the stage and cursor move
    t = next(t for qid, t in _transitions() if t["id"] == _flag()["set_by"]["transition"])
    assert t["effects"][0] == {"kind": "function", "function": GRANT}
    sets = {e["field"]: e["value"] for e in t["effects"] if e.get("kind") == "set_progression"}
    assert sets.get("quest.main_worldshift_reveal.stage") == "rift_released"
    conds = [(c.get("kind"), c.get("field"), c.get("value")) for c in t["conditions"]]
    assert ("progression_equals", "quest.main_worldshift_reveal.stage", "rift_crisis_pending") in conds


def test_nothing_else_in_data_names_the_grant_function_or_grants_the_advancement():
    # a second caller would be a second setter; a raw `advancement grant` would be a setter no ledger knows about
    # (prose mentioning the function is allowed; a record whose `function` value IS it is a call)
    callers = []
    for path in sorted(DATA.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        callers += [path.name for d in _walk(json.loads(text)) if d.get("function") == GRANT]
        assert not re.search(r"advancement grant \S+ only %s\b" % re.escape(ADV), text), path.name
    assert callers == ["quests.json"]


def test_generator_emits_the_grant_function_and_it_grants_exactly_this_advancement():
    out = _real_pack()
    fn = out["data/cobblers/function/flag/%s/grant.mcfunction" % FLAG]
    commands = [l for l in fn.splitlines() if l.strip() and not l.startswith("#")]
    assert commands == ["advancement grant @s only %s" % ADV]


def test_the_advancement_can_only_be_set_by_the_grant_function():
    out = _real_pack()
    adv = json.loads(out["data/cobblers/advancement/flag/%s.json" % FLAG])
    assert [c["trigger"] for c in adv["criteria"].values()] == ["minecraft:impossible"]
    assert adv["rewards"]["function"] == "cobblers:flag/%s/granted" % FLAG
    # no /trigger objective and no tick grant for it: typing a command must not set the finale
    every = "\n".join(t for r, t in out.items() if r.endswith(".mcfunction") and not r.endswith("/grant.mcfunction"))
    assert ("only %s\n" % ADV) not in every + "\n" and ("only %s " % ADV) not in every


def test_only_quest_transition_flags_get_a_grant_function():
    out = _real_pack()
    grants = sorted(r for r in out if r.endswith("/grant.mcfunction"))
    kinds = {f["id"]: f["set_by"]["kind"] for f in _json("progression.json")["flags"]}
    assert grants == sorted("data/cobblers/function/flag/%s/grant.mcfunction" % fid
                            for fid, k in kinds.items() if k == "quest_transition")


def test_invoked_by_matches_the_conversations_that_invoke_the_transition():
    set_by = _flag()["set_by"]
    invokers = []
    for conv in _json("dialogue.json")["conversations"]:
        for d in _walk(conv.get("nodes")):
            if d.get("kind") == "quest_transition" and d.get("transition") == set_by["transition"]:
                invokers.append(conv["id"])
    want = [set_by["invoked_by"]] if set_by.get("invoked_by") else []
    assert sorted(set(invokers)) == want, (
        "data/progression.json %s set_by.invoked_by says %r but the conversations invoking %s are %r"
        % (FLAG, set_by.get("invoked_by"), set_by["transition"], sorted(set(invokers))))
    assert len(invokers) <= 1, "the release is one authored beat: %r invoke it" % invokers
    if not want:
        assert set_by.get("invoked_by_owed"), "an uninvoked setter must say what owes the invoker"


def test_the_dialogue_compiler_compiles_the_transition_with_the_grant_before_the_stage():
    # nothing invokes the transition yet, so `--all` never compiles it; compile it directly, as the release
    # conversation will, under a conversation of the same quest
    import compile_dialogue as CD
    dialogue, quests, fields = CD.load(DATA)
    set_by = _flag()["set_by"]
    conv = next(c for c in dialogue["conversations"] if c.get("quest_id") == set_by["quest"])
    body = CD.Compiler(conv, quests[set_by["quest"]], fields).transition(set_by["transition"])
    call = "' at @s run function %s'" % GRANT
    assert body.count(call) == 1
    assert body.index(call) < body.index("'rift_released'")


def test_plan_rejects_a_quest_transition_flag_without_ids():
    doc = PP.load(DATA / "progression.json")
    for bad in ({"kind": "quest_transition"}, {"kind": "quest_transition", "quest": "main_worldshift_reveal"},
                {"kind": "quest_transition", "quest": "Bad Id", "transition": "x"}):
        d = json.loads(json.dumps(doc))
        next(f for f in d["flags"] if f["id"] == FLAG)["set_by"] = bad
        try:
            PP.plan(d, placements=_json("placements.json"))
        except PP.ProgressionError as e:
            assert "quest_transition" in str(e)
        else:
            raise AssertionError("plan accepted %r" % bad)
