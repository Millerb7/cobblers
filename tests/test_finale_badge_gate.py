"""The finale badge gate (the owner, 2026-10-07, review N8: "no player reaches the finale without a badge").

Written by the test author for unit A3 of Wave A, which another agent built (f788300). What is judged, and from where:

  the badge      data/quests.json main_worldshift_reveal beats[league].requires_existing_flag (the badge the League
                 beat needs), not the relic data's geometry.hq.guard.admit.requires_flag, which the generator reads
  the stage      every transition anywhere in data/quests.json that moves quest.main_worldshift_reveal.stage INTO the
                 finale band (rift_crisis_pending and every later value of data/progression.json's enum) from outside
                 it must require that badge; a transition that only moves a player already inside the band need not
  the surveyor   dlg_main_rift_surveyor's entry rules, evaluated here by a small model of the authored conditions: a
                 player at his locked node without the badge hears the locked line, a badge holder hears the account
  the door       the BUILT hq_admit function (tools/relic_underground.guard_functions, the code under test), run by a
                 tiny interpreter that knows only the command shapes the function may use and fails on any other:
                 a player without the badge's advancement is not moved and gets no admit score; one with all eight is

Not covered: that any of it happens in game. The flag's advancement is granted by rctmod's defeat count
(tools/progression_pack.py, EXP-027) and the condition is probed by compile_dialogue's advancement tag, neither run
here; the tellraw's text component is not parsed by Minecraft here; and a legacy player's saved cursor is modelled,
not read from any world.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import relic_underground as R  # noqa: E402  (the generator under test, never the expectation)

STAGE = "quest.main_worldshift_reveal.stage"
FIRST = "rift_crisis_pending"


def _doc(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


QUESTS = _doc("quests.json")
PROG = _doc("progression.json")
SPEC = _doc("relic_underground.json")
CONVS = {c["id"]: c for c in _doc("dialogue.json")["conversations"]}
MAIN = next(q for q in QUESTS["quests"] if q["id"] == "main_worldshift_reveal")
ORDER = next(f for f in PROG["quest_fields"] if f["id"] == STAGE)["allowed_values"]
BAND = ORDER[ORDER.index(FIRST):]
BADGE = next(b for b in MAIN["beats"] if b["id"] == "league")["requires_existing_flag"]
EIGHT = frozenset(f["id"] for f in PROG["flags"] if re.fullmatch(r"gym[1-8]_cleared", f["id"]))
NS = PROG["namespace"]


def _transitions():
    return [t for q in QUESTS["quests"] for t in q.get("transitions") or []]


def _stage_values(conds):
    """The stages a transition's conditions admit, or None when they do not test the stage."""
    allowed = None
    for c in conds:
        if c.get("field") != STAGE:
            continue
        vals = {c["value"]} if c["kind"] == "progression_equals" else set(c["values"])
        allowed = vals if allowed is None else allowed & vals
    return allowed


# Without it the tests below would compare against an empty band or a badge the data no longer declares.
def test_the_gate_inputs_are_whole():
    assert BADGE in {f["id"] for f in PROG["flags"]}, BADGE
    assert len(EIGHT) == 8 and BADGE in EIGHT
    assert BAND[0] == FIRST and len(BAND) >= 2


# Without it a new or edited transition could move a badgeless player into the finale, which is review N8 again.
def test_no_transition_moves_a_player_into_the_finale_without_the_earth_badge():
    entries = []
    for t in _transitions():
        into = [e["value"] for e in t.get("effects") or []
                if e.get("kind") == "set_progression" and e.get("field") == STAGE and e.get("value") in BAND]
        if not into:
            continue
        conds = t.get("conditions") or []
        reads = _stage_values(conds)
        if reads is not None and reads <= set(BAND):
            continue        # moves a player already inside the band: the badge was needed to get there
        entries.append(t["id"])
        assert {"kind": "flag", "flag": BADGE} in conds, (
            "%s moves the stage to %s from outside the finale without %s" % (t["id"], into, BADGE))
    # the story setter (the surveyor's rift_007) and the badge carry (Nia's entry rule); a third is fine if gated
    assert {"record_rift_crisis_pending", "carry_by_%s_to_%s" % (BADGE, FIRST)} <= set(entries), entries


# --------------------------------------------------------------------------- the surveyor

def _holds(c, st):
    k = c["kind"]
    if k == "always":
        return True
    if k == "all":
        return all(_holds(x, st) for x in c["conditions"])
    if k == "any":
        return any(_holds(x, st) for x in c["conditions"])
    if k == "not":
        return not _holds(c["condition"], st)
    if k == "progression_equals":
        return st.get(c["field"]) == c["value"]
    if k == "progression_in":
        return st.get(c["field"]) in c["values"]
    if k == "flag":
        return c["flag"] in st["flags"]
    if k == "starter_chosen":
        return st["starter"]
    raise AssertionError("condition kind %s is not modelled by this test" % k)


def _opens(cid, stage, flags, cursor=None, starter=True):
    """The node a player opens conversation cid on: its saved cursor (else the initial node), then the entry rule of
    lowest priority whose condition holds, '$cursor' meaning the saved one."""
    conv = CONVS[cid]
    cur = conv["cursor"]
    saved = cursor or cur["initial_node"]
    st = {STAGE: stage, cur["progression_field"]: saved, "flags": frozenset(flags), "starter": starter}
    rule = next(r for r in sorted(conv["entry_rules"], key=lambda r: r["priority"]) if _holds(r["when"], st))
    return saved if rule["node"] == "$cursor" else rule["node"]


SURVEYOR = "dlg_main_rift_surveyor"


# Without it the watch officer's account alone (no badge) would open the surveyor's account again, whose last line is
# the finale's first stage; and a badge holder could be held at the locked line forever.
@pytest.mark.parametrize("stage", ["blaine_reveal_complete", "giovanni_reveal_complete"])
def test_the_surveyor_opens_his_account_only_to_an_earth_badge_holder(stage):
    locked = CONVS[SURVEYOR]["cursor"]["initial_node"]
    assert _opens(SURVEYOR, stage, set()) == locked
    assert _opens(SURVEYOR, stage, EIGHT - {BADGE}) == locked
    first = _opens(SURVEYOR, stage, EIGHT)
    assert first != locked, (stage, first)
    nodes = {n["id"]: n for n in CONVS[SURVEYOR]["nodes"]}
    # the account he opens reaches the line that runs the story setter
    seen, nid = set(), first
    while nid not in seen and nodes[nid]["kind"] == "line":
        seen.add(nid)
        if any(a.get("transition") == "record_rift_crisis_pending" for a in nodes[nid].get("actions_after_acknowledge") or []):
            break
        nid = nodes[nid]["next"]
    else:
        raise AssertionError("the account from %s never runs record_rift_crisis_pending" % first)


# Without it a player told "bring the badge" would not be told WHICH badge, or would be sent to the watch's report.
def test_the_surveyors_locked_line_names_the_earth_badge_and_nothing_else_that_opens_it():
    nodes = {n["id"]: n for n in CONVS[SURVEYOR]["nodes"]}
    text = nodes[CONVS[SURVEYOR]["cursor"]["initial_node"]]["text"]
    assert "Earth Badge" in text and "report" not in text, text


# Without it a badge holder whose saved surveyor cursor is already past the lock (a player who heard his account
# before 2026-10-07 without the badge: the setter then refused silently and the cursor moved on to the repeat) would
# have no conversation left that moves them into the finale.
@pytest.mark.parametrize("cursor", [n["id"] for n in CONVS[SURVEYOR]["nodes"] if n["id"] != "rift_locked"])
def test_a_badge_holder_the_surveyor_has_passed_is_still_carried_into_the_finale(cursor):
    st = {STAGE: "giovanni_reveal_complete", "flags": EIGHT, "starter": True,
          CONVS[SURVEYOR]["cursor"]["progression_field"]: cursor}
    trans = {t["id"]: t for t in _transitions()}
    movers = []
    for cid in MAIN["dialogue_ids"]:
        conv = CONVS[cid]
        cur = conv.get("cursor") or {}
        st_c = dict(st)
        st_c.setdefault(cur.get("progression_field"), cur.get("initial_node"))
        for r in sorted(conv["entry_rules"], key=lambda r: r["priority"]):
            if not _holds(r["when"], st_c):
                continue
            for a in r.get("actions") or []:
                t = trans.get(a.get("transition"))
                if t and all(_holds(c, st_c) for c in t["conditions"]) and any(
                        e.get("field") == STAGE and e.get("value") == FIRST for e in t["effects"]):
                    movers.append((cid, t["id"]))
            break   # only the first rule that holds is taken
    assert movers, "a badge holder with the surveyor cursor at %s is never moved to %s" % (cursor, FIRST)


# --------------------------------------------------------------------------- the door

def _run(lines, pos, flags):
    """Run hq_admit as one player at pos holding flags (progression flag ids). Returns (pos, scores, said). Knows only
    the shapes the function may use; any other line fails the test, so a new command cannot slip past unmodelled."""
    scores, said = {}, []
    near = re.compile(r"^execute unless entity @s\[x=(-?\d+),y=(-?\d+),z=(-?\d+),distance=\.\.(\d+(?:\.\d+)?)\] run (.+)$")
    adv = re.compile(r"^execute unless entity @s\[advancements=\{([a-z0-9_]+):flag/([a-z0-9_]+)=true\}\] run (.+)$")

    def do(cmd):
        nonlocal pos
        if cmd == "return fail":
            return False
        if cmd.startswith("tellraw @s "):
            said.append(json.loads(cmd[len("tellraw @s "):])["text"])
        elif cmd == "ride @s dismount":
            pass
        elif cmd.startswith("tp @s "):
            x, y, z = (float(v) for v in cmd.split()[2:5])
            pos = (x, y, z)
        elif re.fullmatch(r"scoreboard players set @s \S+ -?\d+", cmd):
            _s, _p, _set, _who, obj, val = cmd.split()
            scores[obj] = int(val)
        else:
            raise AssertionError("hq_admit command not modelled: %r" % cmd)
        return True

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m, a = near.match(line), adv.match(line)
        if m:
            gx, gy, gz, d = (float(v) for v in m.groups()[:4])
            if math.dist(pos, (gx, gy, gz)) > d and not do(m.group(5)):
                break
        elif a:
            if not (a.group(1) == NS and a.group(2) in flags) and not do(a.group(3)):
                break
        elif not do(line):
            break
    return pos, scores, said


def _at_guard():
    gx, gy, gz = SPEC["geometry"]["hq"]["guard"]["at"]
    return (gx + 0.5, gy, gz - 0.5)


ADMIT = SPEC["zone"]["pass"]["admit"]["objective"]


# Without it the HQ guard would let a badgeless player who reached the stage before the setters were gated (or by a
# setter added later) through the shut door to the relic hall and Hoopa's cradle.
@pytest.mark.parametrize("flags", [set(), EIGHT - {BADGE}], ids=["no badges", "seven badges, not the Earth Badge"])
def test_a_badgeless_admit_is_refused(flags):
    start = _at_guard()
    pos, scores, said = _run(R.guard_functions(SPEC)["hq_admit"], start, flags)
    assert pos == start, "moved to %s" % (pos,)
    assert ADMIT not in scores, scores
    assert said and "Earth Badge" in said[0], said


# Without it the badge lock could refuse the players it exists to admit (a misspelt flag, a wrong namespace, a lock
# on a flag no setter asks for), and the eight-badge player would be trapped at the door.
def test_an_eight_badge_admit_is_moved_inside_and_admitted():
    landing = tuple(SPEC["geometry"]["hq"]["guard"]["inside_landing"])
    pos, scores, said = _run(R.guard_functions(SPEC)["hq_admit"], _at_guard(), EIGHT)
    assert tuple(math.floor(v) for v in pos) == landing, pos
    assert scores.get(ADMIT) == 1, scores
    assert said == [], said


# Without it the lock could test the badge only when the player is near (or the reach only when badgeless) and a
# player far from the guard would be moved: the reach still refuses everyone away from the guard.
def test_an_eight_badge_player_away_from_the_guard_is_not_moved():
    gx, gy, gz = SPEC["geometry"]["hq"]["guard"]["at"]
    far = (gx + 40.0, gy, gz)
    pos, scores, _said = _run(R.guard_functions(SPEC)["hq_admit"], far, EIGHT)
    assert pos == far and ADMIT not in scores
