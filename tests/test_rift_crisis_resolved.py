"""rift_crisis_resolved: the Rift finale's flag has exactly one setter, and the setter is emitted.

The chain, each link read from its own file rather than from the generator that emits the next:

  data/progression.json   flags[rift_crisis_resolved].set_by = quest_transition (quest, transition, invoked_by)
  data/quests.json        that transition's effects call cobblers:flag/rift_crisis_resolved/grant, and NO other
                          transition, effect or record anywhere in data/ names that function
  tools/progression_pack  emits the grant function, whose one command grants exactly that advancement, and the
                          advancement's only criterion is minecraft:impossible (nothing but the function sets it)
  data/dialogue.json      the conversations that invoke the transition are exactly set_by.invoked_by: since
                          2026-10-03 dlg_main_relic_hall_release, the Compact binder in Hoopa's cradle (the owner:
                          "set it ourselves at the quest stage that ends the Rift crisis"), at ONE node
  data/relic_underground  geometry.release seats that binder, tools/relic_underground.npc_placements() emits it and
                          tools/reapply.py step R18RU places it, in the carved cradle on its fifth stand (at the
                          hall's relic ring until the cradle was carved, 2026-10-03)
  per player              the conversation, the stage field and the grant are all the talking player's own

Not covered: that the transition fires in game (nobody has released Hoopa on a server), that `advancement grant`
from a compiled dialogue's run_command reaches the player (the same construct as the relic HQ guard's hq_admit,
itself unobserved), and Codex's multiplayer "one release advances every eligible player" (not built; per player
like every flag). WRITTEN BY THE IMPLEMENTER of the binder (minecraft-systems-dev, 2026-10-03) at the caller's
request, against CLAUDE.md principle 16's preference: a separate reviewer should read the beat tests below.
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
    # compiled directly, under a conversation of the same quest, so the check does not depend on the invoker
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


# ------------------------------------------------------------------ the beat: the binder's release (2026-10-03)

STAGE = "quest.main_worldshift_reveal.stage"
PENDING = "rift_crisis_pending"
# since 2026-10-04 the release also waits on the confrontation (data/finale_trainers.json): this player has beaten
# Brann and Elara in the cradle. The stage alone no longer opens it
AT_STAGE = {"kind": "progression_equals", "field": STAGE, "value": PENDING}
READY = {"kind": "all", "conditions": [
    AT_STAGE,
    {"kind": "progression_equals", "field": "quest.main_worldshift_reveal.brann_defeated", "value": True},
    {"kind": "progression_equals", "field": "quest.main_worldshift_reveal.elara_defeated", "value": True}]}


def _calls(transition):
    """[(file, conversation or scene id, where)] for every place in data/dialogue.json and data/scenes.json that
    runs `transition`: an entry rule's actions, a line's actions_after_acknowledge, a response's actions, a scene
    zone's transitions."""
    out = []
    for conv in _json("dialogue.json")["conversations"]:
        for rule in conv.get("entry_rules") or []:
            for a in rule.get("actions") or []:
                if a.get("kind") == "quest_transition" and a.get("transition") == transition:
                    out.append(("dialogue.json", conv["id"], "entry rule %s" % rule.get("node")))
        for n in conv.get("nodes") or []:
            for a in n.get("actions_after_acknowledge") or []:
                if a.get("kind") == "quest_transition" and a.get("transition") == transition:
                    out.append(("dialogue.json", conv["id"], "line %s" % n["id"]))
            for r in n.get("responses") or []:
                for a in r.get("actions") or []:
                    if a.get("kind") == "quest_transition" and a.get("transition") == transition:
                        out.append(("dialogue.json", conv["id"], "response %s/%s" % (n["id"], r["id"])))
    for sc in _json("scenes.json")["scenes"]:
        for d in _walk(sc.get("zones")):
            if transition in (d.get("transitions") or []):
                out.append(("scenes.json", sc["id"], "zone"))
    return out


def _conv():
    cid = _flag()["set_by"]["invoked_by"]
    return next(c for c in _json("dialogue.json")["conversations"] if c["id"] == cid)


def test_exactly_one_beat_grants_the_flag_and_only_behind_release_hoopa_at_the_crisis_stage():
    # one node in all of data runs the setter: the binder's release line
    set_by = _flag()["set_by"]
    assert _calls(set_by["transition"]) == [("dialogue.json", set_by["invoked_by"], "line release_001")]
    conv = _conv()
    nodes = {n["id"]: n for n in conv["nodes"]}
    # the only way onto release_001 is the response "Release Hoopa.", shown only at rift_crisis_pending ...
    into = [(n["id"], r) for n in conv["nodes"] for r in n.get("responses") or [] if r.get("next") == "release_001"]
    into += [(n["id"], None) for n in conv["nodes"] if n.get("next") == "release_001"]
    assert [(nid, r["text"]) for nid, r in into] == [("bound_004", "Release Hoopa.")]
    assert into[0][1]["visible_when"] == READY
    # ... reached from the one entry rule that reads rift_crisis_pending AND both wins, by plain lines
    entry = [r for r in conv["entry_rules"] if r["node"] == "bound_001"]
    assert [r["when"] for r in entry] == [READY]
    walk, seen = "bound_001", []
    while nodes[walk]["kind"] == "line":
        seen.append(walk)
        walk = nodes[walk]["next"]
    assert walk == "bound_004" and seen == ["bound_001", "bound_002", "bound_003"]
    # and the transition itself refuses any other stage, so a released player re-talking cannot re-run it, and a
    # player who has not beaten both cannot run it whatever page they reach
    t = next(t for _q, t in _transitions() if t["id"] == set_by["transition"])
    assert t["conditions"] == READY["conditions"]


def test_the_stage_the_release_needs_is_set_in_play_and_admits_the_player_to_the_hall():
    # rift_crisis_pending is written by a transition a placed conversation invokes (the Rift surveyor's rift_007) ...
    setters = [t["id"] for _q, t in _transitions()
               if any(e.get("kind") == "set_progression" and e.get("field") == STAGE and e.get("value") == PENDING
                      for e in t.get("effects") or [])]
    assert setters == ["record_rift_crisis_pending"]
    assert _calls("record_rift_crisis_pending") == [("dialogue.json", "dlg_main_rift_surveyor", "line rift_007")]
    # ... and the HQ guard, the hall's one way in, admits a player at that stage
    relic = _json("relic_underground.json")
    assert PENDING in relic["geometry"]["hq"]["guard"]["stages"]
    admit = next(t for _q, t in _transitions() if t["id"] == "relic_hq_admit")
    assert any(c.get("kind") == "progression_in" and PENDING in c.get("values", []) for c in admit["conditions"])


def _seat_problems(seat, spec):
    # since 2026-10-03 the binder stands in the carved cradle (geometry.cradle.carve true), on a stand of
    # composition.cradle; the route to every stand is tools/relic_underground_audit.py's (its "cradle" and "release")
    import math
    import relic_underground as R
    geo = R.Geo(spec)
    assert geo.cradle, "the cradle is not carved: the binder has no cradle to stand in"
    cells = R.cradle_composition(geo, spec)
    x, y, z = seat
    out = []
    r = geo.carved_range(x, z)
    if r is None or not geo.in_cradle(x, z) or not (geo.cfloor < y and y + 2 <= r[1]):
        out.append("not in the cradle's air")
    if y - 1 != geo.cfloor:
        out.append("not on the cradle's floor")
    if any((x, y + d, z) in cells for d in (0, 1, 2)):
        out.append("a block the cradle builds in its feet or head")
    st = spec["composition"]["cradle"]["stands"]
    cx, cz = spec["geometry"]["cradle"]["centre"]
    stands = [(int(round(cx + st["orbit"] * math.cos(math.radians(b)))), geo.cfloor + 1,
               int(round(cz + st["orbit"] * math.sin(math.radians(b))))) for b in st["bearings"]]
    if tuple(seat) not in stands:
        out.append("not one of the cradle's stands")
    elif len(stands) - 1 < 4:
        out.append("takes one of Codex's four player stands")
    return out


def test_the_releasing_npc_is_placed_by_a_step_in_the_carved_cradle():
    import relic_underground as R
    spec = R.load()
    rel = spec["geometry"]["release"]
    conv = _conv()
    assert conv["npc_id"] == rel["npc"] and conv["id"] == rel["conversation"]
    # npc_placements() emits it, and tools/reapply.py's R18RU places exactly npc_placements()
    placed = [(c, xyz, cls) for c, xyz, cls, _yaw in R.npc_placements(spec)]
    assert (conv["id"], tuple(rel["at"]), "cobblers:%s" % rel["npc"]) in placed
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    step = src[src.index('("R18RU"'):]
    step = step[:step.index("out.append", 1)]
    assert '[("npc", n) for n in relic_underground.npc_placements()]' in step
    # on one of the cradle's stands, on its floor, two clear over its feet, leaving Codex's four for players
    assert _seat_problems(tuple(rel["at"]), spec) == []


def test_the_seat_check_refuses_a_seat_on_a_pylon_and_one_off_the_stands():
    # without this the check above could pass by checking nothing: a pylon (composition.cradle.pylons, bearing 45,
    # orbit 6) fills its cell, the cradle's centre is the actor marker and no stand, and the hall is no longer the seat
    import relic_underground as R
    spec = R.load()
    geo = R.Geo(spec)
    cx, cz = spec["geometry"]["cradle"]["centre"]
    px, pz = R._at(geo.cc, spec["composition"]["cradle"]["pylons"]["orbit"], 45)
    assert "a block the cradle builds in its feet or head" in _seat_problems((px, 13, pz), spec)
    assert "not one of the cradle's stands" in _seat_problems((cx, 13, cz), spec)
    hx, hz = spec["geometry"]["hall"]["centre"]
    assert "not in the cradle's air" in _seat_problems((hx, 8, hz + 6), spec)


def test_the_flag_is_per_player_as_built():
    import compile_dialogue as CD
    conv = _conv()
    assert conv["scope"] == "player"
    fields = {f["id"]: f for f in _json("progression.json")["quest_fields"]}
    assert fields[STAGE]["scope"] == "player"
    assert fields[conv["cursor"]["progression_field"]]["scope"] == "player"
    dialogue, quests, flds = CD.load(DATA)
    files = CD.compile_conversation(conv, quests, flds)
    page = next(p for p in files["data/cobblers/dialogues/%s.json" % conv["id"]]["pages"] if p["id"] == "release_001")
    body = page["input"]
    # the grant runs as and at the talking player, and nothing in the page names another player
    assert "'execute as ' + q.player.uuid + ' at @s run function %s'" % GRANT in body
    assert not re.search(r"@[aepr]\b", body)
    assert body.index(GRANT) < body.index("'rift_released'")
    # the grant itself is @s only (the generator's one command)
    fn = _real_pack()["data/cobblers/function/flag/%s/grant.mcfunction" % FLAG]
    assert [l for l in fn.splitlines() if l.strip() and not l.startswith("#")] == ["advancement grant @s only %s" % ADV]
