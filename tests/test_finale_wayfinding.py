"""The Rift finale's way-finding: at each stage of the chain from the HQ's ring-0 door to rift_crisis_resolved, the
person a player meets says where the NEXT stop is (docs/world-building/RIFT_FINALE_CHAIN.md).

Written by the finale builder, 2026-10-05, for its own two line changes in data/dialogue.json: the ring-0 guard's
admit_pending (a player at rift_crisis_pending is let into the HQ and turned back by Elara, and until then nothing at
the HQ named Nia, whose handoff is the next stage) and the binder's confront_003 (which sent a player to Elara's
office after she moved to the tower's door). It is not the chain's audit: tools/finale_audit.py executes the compiled
conversations; this reads the authored ones and asks only what a player is told.

What a player hears at a stage: the conversation's entry rule of lowest priority number whose condition holds, then
that node's `next` chain of lines (each line shown once) up to and including the first choice. The stage values come
from data/progression.json, so a renamed stage fails here instead of silently matching nothing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STAGE = "quest.main_worldshift_reveal.stage"


def _doc(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


CONVS = {c["id"]: c for c in _doc("dialogue.json")["conversations"]}


def _stages():
    f = next(f for f in _doc("progression.json")["quest_fields"] if f["id"] == STAGE)
    return f["allowed_values"]


def _badges():
    """The eight gym badge flags, from data/progression.json (gym<N>_cleared)."""
    out = sorted(f["id"] for f in _doc("progression.json")["flags"] if re.fullmatch(r"gym[1-8]_cleared", f["id"]))
    assert len(out) == 8, out
    return frozenset(out)


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
        return state.get("starter", False)
    raise AssertionError("condition kind %s is not modelled by this test" % k)


def heard(conv_id, stage, flags=None, starter=True):
    """The texts a player at `stage` (every other field unset) hears on opening the conversation. Since 2026-10-07
    (review N8) only an Earth Badge holder reaches rift_crisis_pending, so the default player holds all eight badges
    and a starter; the badge carries read only stages before the finale's, so none of them fires here."""
    c = CONVS[conv_id]
    state = {STAGE: stage, "flags": _badges() if flags is None else frozenset(flags), "starter": starter}
    rule = next(r for r in sorted(c["entry_rules"], key=lambda r: r["priority"]) if _holds(r["when"], state))
    nodes = {n["id"]: n for n in c["nodes"]}
    out, seen, nid = [], set(), rule["node"]
    while nid and nid not in seen:
        seen.add(nid)
        n = nodes[nid]
        out.append(n.get("text", ""))
        if n["kind"] != "line":
            break
        nid = n.get("next")
    return " ".join(out)


# (conversation, stage, words the player must hear, which next stop the words name)
POINTERS = [
    ("dlg_main_relic_hq_guard", "rift_crisis_pending", ["Nia Calder", "two rings down"],
     "Nia's clinic: the next stage is her handoff, and the HQ admits a player before it"),
    ("dlg_main_relic_hall_release", "rift_crisis_pending", ["door", "Nia Calder"],
     "a player who went down to the cradle first is sent to Nia and to Elara at the door"),
    ("dlg_main_relic_hall_release", "deep_handoff_received", ["briefing hall"], "Brann"),
    ("dlg_main_finale_nia", "rift_crisis_pending", ["Headquarters", "door"], "the HQ tower's door, after her handoff"),
    ("dlg_main_finale_elara", "deep_handoff_received", ["briefing hall"], "Brann, up the tower"),
    ("dlg_main_finale_brann", "hq_crossed", ["Anchor control", "door"], "Oren at the top, then Elara at the door"),
    ("dlg_main_finale_oren", "anchor_shutdown", ["Elara holds the door"], "Elara at the door"),
    ("dlg_main_finale_elara", "cradle_open", ["passage beneath the relic site"], "the stair and the cradle"),
]


@pytest.mark.parametrize("conv,stage,words,why", POINTERS, ids=["%s@%s" % (p[0], p[1]) for p in POINTERS])
def test_each_stop_names_the_next(conv, stage, words, why):
    assert stage in _stages(), "%s is not a stage in data/progression.json" % stage
    text = heard(conv, stage)
    missing = [w for w in words if w not in text]
    assert not missing, "%s at %s does not name %s (%s): heard %r" % (conv, stage, missing, why, text)


def test_nobody_sends_a_player_to_elaras_office():
    """Elara left the director's office for the tower's door (data/hq_tower.json door_keeper, superseded_at hq_s9);
    a finale line that still places her in the office sends a player up eleven storeys to an empty room."""
    door = _doc("hq_tower.json")["door_keeper"]
    assert door["npc"] == "npc_finale_elara_venn"
    finale = [c for cid, c in CONVS.items() if cid.startswith(("dlg_main_finale_", "dlg_main_relic_"))]
    stale = ["%s/%s" % (c["id"], n["id"]) for c in finale for n in c["nodes"] if "in her office" in n.get("text", "")]
    assert not stale, stale


def test_the_guard_still_admits_after_the_pointer():
    """The pointer line leads into the admit choice; it never replaces it (the 'Go through.' option is the only way
    into the HQ's room, data/relic_underground.json geometry.hq.guard)."""
    c = CONVS["dlg_main_relic_hq_guard"]
    nodes = {n["id"]: n for n in c["nodes"]}
    assert nodes["admit_pending"]["next"] == "admit"
    assert any(r["id"] == "r_go" for r in nodes["admit"]["responses"])
    assert heard("dlg_main_relic_hq_guard", "rift_crisis_pending").endswith(nodes["admit"]["text"])
    assert heard("dlg_main_relic_hq_guard", "deep_handoff_received") == nodes["admit"]["text"]
