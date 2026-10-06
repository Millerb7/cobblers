"""After gym 8 the player is told where to go, and Victory Road and the Rift finale are explained in the world
(the owner, 2026-10-06: "A player who beats gym 8 needs to know where to go"; docs/world-building/POST_GYM8_DIRECTION.md).

Written by the direction builder for its own lines in data/dialogue.json: the southern watch's giovanni_way, the Rift
surveyor's rift_way_1..3 and rift_after, and the binder's release_way, with the entry rules that show them. Like
tests/test_finale_wayfinding.py this reads the AUTHORED conversations and asks only what a player is told; it is not
the chain's audit (tools/finale_audit.py executes the compiled ones).

What a player hears: the entry rule of lowest priority number whose condition holds for the player's state (stage,
cursors, held flags), then that node's `next` chain of lines, each shown once, up to the first choice. `$cursor` is the
conversation's cursor field, or its initial node when unset.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
Q = "quest.main_worldshift_reveal."
STAGE = Q + "stage"


def _doc(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


CONVS = {c["id"]: c for c in _doc("dialogue.json")["conversations"]}
STAGES = next(f for f in _doc("progression.json")["quest_fields"] if f["id"] == STAGE)["allowed_values"]


def _holds(cond, state):
    k = cond["kind"]
    if k == "always":
        return True
    if k == "all":
        return all(_holds(c, state) for c in cond["conditions"])
    if k == "progression_equals":
        return state.get(cond["field"]) == cond["value"]
    if k == "progression_in":
        return state.get(cond["field"]) in cond["values"]
    if k == "flag":
        return cond["flag"] in state.get("flags", ())
    if k == "starter_chosen":
        return True
    raise AssertionError("condition kind %s is not modelled by this test" % k)


def heard(conv_id, **state):
    """The texts a player in `state` hears on opening the conversation. Keys: stage, cursor, flags."""
    c = CONVS[conv_id]
    s = {STAGE: state.get("stage"), "flags": set(state.get("flags", ()))}
    cur = c.get("cursor") or {}
    if cur:
        s[cur["progression_field"]] = state.get("cursor", cur["initial_node"])
    for v in s.values():
        assert v is None or isinstance(v, set) or v in STAGES or v in {n["id"] for n in c["nodes"]}, v
    rule = next(r for r in sorted(c["entry_rules"], key=lambda r: r["priority"]) if _holds(r["when"], s))
    nodes = {n["id"]: n for n in c["nodes"]}
    nid = s[cur["progression_field"]] if rule["node"] == "$cursor" else rule["node"]
    out, seen = [], set()
    while nid and nid not in seen:
        seen.add(nid)
        n = nodes[nid]
        out.append(n.get("text", ""))
        if n["kind"] != "line":
            break
        nid = n.get("next")
    return " ".join(out)


def _has(text, *words):
    missing = [w for w in words if w.lower() not in text.lower()]
    assert not missing, "missing %s in: %s" % (missing, text)


# ---------------------------------------------------------------- the Earth Badge to the Rift surveyor

def test_an_earth_badge_holder_back_at_the_southern_watch_is_sent_to_the_rift_surveyor():
    t = heard("dlg_main_giovanni_watch", stage="giovanni_reveal_complete", cursor="giovanni_repeat",
              flags={"gym8_cleared"})
    _has(t, "Rift surveyor", "trailhead", "Victory Road", "north")


def test_without_the_badge_the_watch_still_repeats_its_own_line():
    t = heard("dlg_main_giovanni_watch", stage="giovanni_reveal_complete", cursor="giovanni_repeat")
    assert "surveyor" not in t, t


def test_the_watch_account_ends_with_the_surveyor_before_the_repeat():
    t = heard("dlg_main_giovanni_watch", stage="blaine_reveal_complete", cursor="giovanni_001")
    _has(t, "containment cradle", "Rift surveyor", "trailhead")
    assert t.index("Rift surveyor") > t.index("containment cradle")


# ---------------------------------------------------------------- the surveyor: the Deep, the HQ, the cradle, Victory Road

def test_the_surveyor_account_names_the_deep_the_hq_the_cradle_and_victory_road():
    t = heard("dlg_main_rift_surveyor", stage="giovanni_reveal_complete", cursor="rift_001")
    _has(t, "the Deep", "Sink Gate", "headquarters", "black tower", "west", "iron door", "containment cradle",
         "Victory Road's caves", "until Hoopa is free")


def test_a_badge_holder_carried_past_giovanni_hears_the_same_account():
    # the badge carry (rule 6) opens the account at rift_001 for a player who never met the watch
    t = heard("dlg_main_rift_surveyor", stage="sabrina_reveal_complete", flags={"gym8_cleared"})
    _has(t, "headquarters", "containment cradle", "Victory Road's caves")


@pytest.mark.parametrize("stage", ["rift_crisis_pending", "deep_handoff_received", "hq_crossed", "anchor_shutdown",
                                   "cradle_open"])
def test_coming_back_to_the_surveyor_mid_crisis_tells_where_the_hq_and_cradle_are(stage):
    t = heard("dlg_main_rift_surveyor", stage=stage, cursor="rift_repeat", flags={"gym8_cleared"})
    _has(t, "headquarters", "iron door", "cradle", "Victory Road")


@pytest.mark.parametrize("cursor", ["rift_repeat", "rift_after"])
def test_after_the_release_the_surveyor_says_the_league_is_open(cursor):
    t = heard("dlg_main_rift_surveyor", stage="rift_released", cursor=cursor, flags={"gym8_cleared"})
    _has(t, "Hoopa is free", "League", "Victory Road")
    assert "before approaching the League" not in t, t


def test_after_the_release_the_binder_says_where_the_game_goes():
    for stage in ("rift_released", "league_recognized"):
        t = heard("dlg_main_relic_hall_release", stage=stage)
        _has(t, "Victory Road", "League", "Deep's floor")


def test_the_release_itself_ends_on_the_way_out():
    c = CONVS["dlg_main_relic_hall_release"]
    nodes = {n["id"]: n for n in c["nodes"]}
    assert nodes["release_003"]["next"] == "release_way"
    assert nodes["release_way"]["next"] == "released_repeat"


# ---------------------------------------------------------------- the lines are ours, marked, and Codex's are intact

OURS = {"dlg_main_giovanni_watch": ["giovanni_way"],
        "dlg_main_rift_surveyor": ["rift_way_1", "rift_way_2", "rift_way_3", "rift_after"],
        "dlg_main_relic_hall_release": ["release_way"]}

CODEX = {("dlg_main_giovanni_watch", "giovanni_007"):
         "After the badge, follow the Rift's south-west arm to its fork, then the trunk toward the head. "
         "The final operation lies above the containment cradle.",
         ("dlg_main_giovanni_watch", "giovanni_repeat"):
         "The loyalists are going to the Rift. The dissenters supplied a route, not a painless answer.",
         ("dlg_main_rift_surveyor", "rift_006"):
         "Reach the cradle, end the forced steering, and release Hoopa. The League will not open while the "
         "activation remains live.",
         ("dlg_main_rift_surveyor", "rift_repeat"):
         "The operation is active above the cradle. End the steering and release Hoopa before approaching the League.",
         ("dlg_main_relic_hall_release", "released_repeat"):
         "The ring is empty. The Rift has stopped widening, but the exchanged world remains."}


def test_every_line_this_build_added_is_marked_for_codex():
    for cid, ids in OURS.items():
        nodes = {n["id"]: n for n in CONVS[cid]["nodes"]}
        for nid in ids:
            p = nodes[nid].get("placeholder") or ""
            assert p.startswith("Claude, 2026-10-06 (the direction builder"), (cid, nid)


def test_codex_lines_are_unchanged():
    for (cid, nid), text in CODEX.items():
        n = next(n for n in CONVS[cid]["nodes"] if n["id"] == nid)
        assert n["text"] == text, (cid, nid)
        assert "placeholder" not in n, (cid, nid)


def test_the_completing_lines_still_complete():
    """Inserting a line after a beat's last line must not move the transition off it."""
    nodes = {n["id"]: n for n in CONVS["dlg_main_giovanni_watch"]["nodes"]}
    assert [a["transition"] for a in nodes["giovanni_007"]["actions_after_acknowledge"]] == ["complete_giovanni_reveal"]
    nodes = {n["id"]: n for n in CONVS["dlg_main_rift_surveyor"]["nodes"]}
    assert [a["transition"] for a in nodes["rift_007"]["actions_after_acknowledge"]] == ["record_rift_crisis_pending"]
    for cid, ids in OURS.items():
        for nid in ids:
            n = next(n for n in CONVS[cid]["nodes"] if n["id"] == nid)
            assert not n.get("actions") and not n.get("actions_after_acknowledge"), (cid, nid)


def test_what_the_lines_claim_about_the_world_matches_the_data():
    vr = _doc("vr_caves.json")
    assert vr["mouth"]["toward"] == "north"          # "climb north from the Deep's floor"
    assert vr["exit"]["at"][1] > vr["mouth"]["at"][1]  # they climb
    z5 = _doc("rift_zones.json")["zones"]["z5"]
    assert z5["pass"]["kind"] == "flag" and z5["pass"]["flags"] == ["rift_crisis_resolved"]  # "until Hoopa is free"
    seats = {s["id"]: s["at"] for s in _doc("npc_seats.json")["seats"]}
    sx, _, sz = seats["npc_main_rift_surveyor"]
    gym8 = _doc("gym_buildings/gym8.json")
    lot = gym8["site"]["lot_rect"]
    assert sz < lot[1] - 900 and abs(sx - (lot[0] + lot[2]) / 2) < 100   # "about a thousand blocks north"
