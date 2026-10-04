"""The Rift finale's confrontation: Brann and Elara in Hoopa's cradle, and the release that waits on them.

WRITTEN BY THE IMPLEMENTER (datapack-content-dev, 2026-10-04) at the caller's request; an independent audit follows.
What is asserted, on the real data and the real generators:

  records   data/finale_trainers.json carries exactly Brann and Elara, each a full record (rct team == team) whose
            `sets` is its own declared, player-scoped boolean field of main_worldshift_reveal, listed in the quest's
            progression_field_refs; no level above the post-gym-8 cap of 60, and Elara's ace at it
  rct data  tools/route_trainers.files(): the won function sets exactly that field to 1 and saves, the advancement
            is rctmod defeat_count for that id at count 1; Brann battles on sight, Elara does not
  seats     each in the cradle's air on its floor, two clear, on no player stand, binder stand or actor marker
            (tools/relic_underground.py Geo and cradle_composition, the cells the build writes)
  gate      the binder's 'Release Hoopa.', its bound_001 entry rule and the setter transition all require the stage
            AND both fields; walking the conversation offline with either field unset never reaches release_001
  compiled  the compiled release page runs the grant only under all three, and the fx last
  fx        cobblers:relic_underground/release_fx is @s-only, spawns nothing and changes no block
  reapply   R18RU places both trainers beside the binder

Not covered: anything in game. Nobody has fought Brann or Elara or released Hoopa on a server; rctmod's sight check
and the defeat advancement are proven for other seats (EXP-027, the mansion guardians), not these.
"""
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import relic_underground as R  # noqa: E402
import route_trainers as RT  # noqa: E402

DATA = ROOT / "data"
STAGE = "quest.main_worldshift_reveal.stage"
PENDING = "rift_crisis_pending"
BRANN, ELARA = "finale_brann_saye", "finale_elara_venn"
FIELD = {BRANN: "quest.main_worldshift_reveal.brann_defeated", ELARA: "quest.main_worldshift_reveal.elara_defeated"}
CAP = 60


def _json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


FINALE = {t["id"]: t for t in _json("finale_trainers.json")["trainers"]}
QUEST = next(q for q in _json("quests.json")["quests"] if q["id"] == "main_worldshift_reveal")
FIELDS = {f["id"]: f for f in _json("progression.json")["quest_fields"]}
CONV = next(c for c in _json("dialogue.json")["conversations"] if c["id"] == "dlg_main_relic_hall_release")
SETTER = next(t for t in QUEST["transitions"] if t["id"] == "unlock_league_after_rift_resolution")
SPEC = R.load()


def test_exactly_brann_and_elara_each_with_its_own_player_field():
    assert sorted(FINALE) == [BRANN, ELARA]
    for tid, t in FINALE.items():
        assert t["sets"] == [FIELD[tid]]
        f = FIELDS[FIELD[tid]]
        assert (f["type"], f["scope"], f["initial"], f["quest_id"]) == ("boolean", "player", False,
                                                                        "main_worldshift_reveal")
        assert FIELD[tid] in QUEST["progression_field_refs"]
        assert t["rct"]["team"] == t["team"]
    # no other trainer record anywhere uses these ids
    assert not set(FINALE) & {r["id"] for r in _json("trainers.json")["trainers"]}


def test_teams_respect_the_post_gym_8_cap_and_elaras_ace_is_at_it():
    for t in FINALE.values():
        levels = [m["level"] for m in t["team"]]
        assert max(levels) <= CAP and min(levels) >= 50, (t["id"], levels)
        assert all(len(m["moveset"]) == 4 for m in t["team"])
    assert max(m["level"] for m in FINALE[ELARA]["team"]) == CAP
    assert max(m["level"] for m in FINALE[BRANN]["team"]) < CAP
    assert len(FINALE[ELARA]["team"]) == 6


@pytest.fixture(scope="module")
def files():
    return RT.files()


def test_rct_data_sets_exactly_the_field_on_a_win_only(files):
    for tid in FINALE:
        won = files["data/cobblers/function/trainers/won/%s.mcfunction" % tid]
        assert any(("t.d.%s = 1;" % CD.key(FIELD[tid])) in l and "save_data" in l for l in won)
        others = [f for f in FIELD.values() if f != FIELD[tid]]
        assert not any(CD.key(o) in l for l in won for o in others)
        adv = files["data/cobblers/advancement/trainer/%s.json" % tid]
        assert adv["criteria"] == {"won": {"trigger": "rctmod:defeat_count",
                                           "conditions": {"trainer_ids": [tid], "count": 1}}}
        trainer = files["data/rctmod/trainers/%s.json" % tid]
        assert trainer["team"] == FINALE[tid]["team"]
    assert files["data/rctmod/mobs/trainers/single/%s.json" % BRANN].get("forceBattleOnSight") is True
    assert "forceBattleOnSight" not in files["data/rctmod/mobs/trainers/single/%s.json" % ELARA]


def test_seats_are_free_cradle_floor_cells():
    geo = R.Geo(SPEC)
    cells = R.cradle_composition(geo, SPEC)
    cr = SPEC["composition"]["cradle"]
    taken = {tuple(cr["actor_marker"]["at"])}
    taken |= {(R._at(geo.cc, cr["stands"]["orbit"], b)[0], geo.cfloor + 1, R._at(geo.cc, cr["stands"]["orbit"], b)[1])
              for b in cr["stands"]["bearings"]}
    assert tuple(SPEC["geometry"]["release"]["at"]) in taken
    seen = set()
    for tid, t in FINALE.items():
        x, y, z = t["seat"]
        r = geo.carved_range(x, z)
        assert geo.in_cradle(x, z) and not geo.in_passage(x, z), tid
        assert y - 1 == geo.cfloor and r is not None and y + 2 <= r[1], tid
        assert not any((x, y + d, z) in cells for d in (0, 1, 2)), tid
        assert (x, y, z) not in taken | seen, tid
        seen.add((x, y, z))
    # Brann's sight stays inside the cradle's radius plus nothing: 8 from his seat is under 17 from the centre
    bx, _by, bz = FINALE[BRANN]["seat"]
    assert math.hypot(bx + 0.5 - geo.cc[0], bz + 0.5 - geo.cc[1]) + FINALE[BRANN]["sight_distance"] <= geo.cr + 1
    # and he sees the cut: some cell of the passage's axis inside the cradle is within his sight
    assert any(math.hypot(bx - x, bz - SPEC["geometry"]["axis_z"]) <= FINALE[BRANN]["sight_distance"]
               for x in range(geo.cc[0], geo.cc[0] + geo.cr + 1))


def _spots(geo):
    cr = SPEC["composition"]["cradle"]
    return [tuple(cr["actor_marker"]["at"])] + [
        (R._at(geo.cc, cr["stands"]["orbit"], b)[0], geo.cfloor + 1, R._at(geo.cc, cr["stands"]["orbit"], b)[1])
        for b in cr["stands"]["bearings"]]


def test_reports_seat_check_passes_the_real_seats_and_bites():
    # report's 4c (relic_underground.finale_seat_problems) is clean on the real seats, and refuses a seat on a pylon,
    # on the binder's stand, in the cut, in the hall, and two trainers on one cell -- so it is not checking nothing
    geo = R.Geo(SPEC)
    cells = R.cradle_composition(geo, SPEC)
    spots = _spots(geo)
    assert R.finale_seat_problems(geo, cells, spots, R.finale_seats()) == []
    px, pz = R._at(geo.cc, SPEC["composition"]["cradle"]["pylons"]["orbit"], 45)
    hx, hz = SPEC["geometry"]["hall"]["centre"]
    for bad in [(px, 13, pz), tuple(SPEC["geometry"]["release"]["at"]), (3366, 13, SPEC["geometry"]["axis_z"]),
                (hx, 13, hz), (3352, 14, 3300)]:
        assert R.finale_seat_problems(geo, cells, spots, [("x", bad)]), bad
    one = tuple(FINALE[BRANN]["seat"])
    assert R.finale_seat_problems(geo, cells, spots, [("a", one), ("b", one)])


READY = [{"kind": "progression_equals", "field": STAGE, "value": PENDING},
         {"kind": "progression_equals", "field": FIELD[BRANN], "value": True},
         {"kind": "progression_equals", "field": FIELD[ELARA], "value": True}]


def test_the_setter_and_the_choice_both_require_the_stage_and_both_wins():
    assert SETTER["conditions"] == READY
    assert SETTER["effects"][0] == {"kind": "function", "function": "cobblers:flag/rift_crisis_resolved/grant"}
    assert SETTER["effects"][-1] == {"kind": "function", "function": "cobblers:relic_underground/release_fx"}
    nodes = {n["id"]: n for n in CONV["nodes"]}
    rel = next(r for r in nodes["bound_004"]["responses"] if r["next"] == "release_001")
    assert rel["visible_when"] == {"kind": "all", "conditions": READY}


def _holds(c, state):
    k = c["kind"]
    if k == "always":
        return True
    if k == "all":
        return all(_holds(x, state) for x in c["conditions"])
    if k == "progression_equals":
        return state.get(c["field"], False) == c["value"]
    if k == "progression_in":
        return state.get(c["field"]) in c["values"]
    raise AssertionError("condition kind %s not modelled" % k)


def _reachable(state):
    """Every node a player in `state` can reach from the entry rules, following lines and visible responses."""
    rules = sorted(CONV["entry_rules"], key=lambda r: r["priority"])
    start = next(r["node"] for r in rules if _holds(r["when"], state))
    nodes = {n["id"]: n for n in CONV["nodes"]}
    seen, todo = set(), [start]
    while todo:
        nid = todo.pop()
        if nid in seen:
            continue
        seen.add(nid)
        n = nodes[nid]
        if n.get("next"):
            todo.append(n["next"])
        for r in n.get("responses") or []:
            if r.get("next") and _holds(r.get("visible_when", {"kind": "always"}), state):
                todo.append(r["next"])
    return seen


@pytest.mark.parametrize("brann,elara", [(False, False), (True, False), (False, True)])
def test_without_both_wins_the_release_is_unreachable(brann, elara):
    state = {STAGE: PENDING, FIELD[BRANN]: brann, FIELD[ELARA]: elara}
    got = _reachable(state)
    assert "release_001" not in got
    assert "confront_001" in got


def test_with_both_wins_at_the_stage_the_release_is_reachable_and_not_after():
    assert "release_001" in _reachable({STAGE: PENDING, FIELD[BRANN]: True, FIELD[ELARA]: True})
    for later in ("rift_released", "league_recognized", "giovanni_reveal_complete"):
        assert "release_001" not in _reachable({STAGE: later, FIELD[BRANN]: True, FIELD[ELARA]: True})


def test_compiled_release_page_grants_only_under_all_three():
    _d, quests, flds = CD.load(DATA)
    out = CD.compile_conversation(CONV, quests, flds)
    page = next(p for p in out["data/cobblers/dialogues/%s.json" % CONV["id"]]["pages"] if p["id"] == "release_001")
    body = page["input"]
    guard = body[:body.index("cobblers:flag/rift_crisis_resolved/grant")]
    for f in FIELD.values():
        assert "t.d.%s == 1" % CD.key(f) in guard
    assert "'%s'" % PENDING in guard
    assert body.index("rift_crisis_resolved/grant") < body.index("relic_underground/release_fx")


def test_release_fx_is_for_the_releasing_player_only():
    fn = R.guard_functions(SPEC)["release_fx"]
    cmds = [l for l in fn if l.strip() and not l.startswith("#")]
    assert cmds[0].startswith("execute unless entity @s[")
    for l in cmds[1:]:
        assert l.split()[0] in ("particle", "playsound", "title"), l
        assert not re.search(r"@[aepr]\b", l), l
    assert any(l.startswith("particle") and l.endswith("force @s") for l in cmds)
    assert any(l.startswith("playsound") and " master @s " in l for l in cmds)


def test_r18ru_places_both_trainers_beside_the_binder():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    step = src[src.index('("R18RU"'):]
    step = step[:step.index("out.append", 1)]
    assert '[("trainer", t) for t in route_trainers.finale_placements()]' in step
    got = RT.finale_placements()
    assert sorted(p[0] for p in got) == [BRANN, ELARA]
    assert {p[0]: p[1] for p in got} == {tid: tuple(t["seat"]) for tid, t in FINALE.items()}
