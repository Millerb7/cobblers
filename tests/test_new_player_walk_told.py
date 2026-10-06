"""new_player_walk's told_where_next (2026-10-06, docs/world-building/POST_GYM8_DIRECTION.md): the Earth Badge's built
reward offers a waypoint on the seat of the NPC who opens the Rift road, and rift_crisis_resolved's offers one inside the
League. Fixtures only: a tmp root's data files and a tmp packs dir with one granted function each."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import new_player_walk as W  # noqa: E402

SEAT = [3552, 112, 5334]


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")


def share(name, x, y, z):
    return ('tellraw @s ["", {"text": "Next: %s. ", "color": "gold"}, {"text": "xaero-waypoint:%s:RS:%d:%d:%d:14:'
            'false:0:Internal-overworld-waypoints", "color": "dark_gray"}]' % (name, name, x, y, z))


def world(tmp, offer=None, seat=SEAT, wired=True):
    root, packs = tmp / "root", tmp / "root" / "packs"
    stage = "quest.main_worldshift_reveal.stage"
    write(root / "data" / "quests.json", {"quests": [{"id": "main_worldshift_reveal", "transitions": [
        {"id": "record_rift_crisis_pending",
         "conditions": [{"kind": "progression_equals", "field": stage, "value": "giovanni_reveal_complete"}],
         "effects": [{"kind": "set_progression", "field": stage, "value": "rift_crisis_pending"}]}]}]})
    node = {"id": "rift_007", "kind": "line", "text": "x"}
    if wired:
        node["actions_after_acknowledge"] = [{"kind": "quest_transition", "transition": "record_rift_crisis_pending"}]
    write(root / "data" / "dialogue.json", {"conversations": [
        {"id": "dlg_main_rift_surveyor", "npc_id": "npc_main_rift_surveyor", "nodes": [node]}]})
    write(root / "data" / "npc_seats.json", {"seats": [{"id": "npc_main_rift_surveyor", "at": seat}]})
    fn = packs / "cobblers_progression" / "data" / "cobblers" / "function" / "flag" / "gym8_cleared" / "granted.mcfunction"
    write(fn, "function cobblers:navigation/reconcile\n" + (share(*offer) + "\n" if offer else ""))
    return W.Inputs(root=root, packs=packs)


def told(inp):
    st = W.Stage("victory_road", "t")
    W.Walker.told_after_gym8(types.SimpleNamespace(inp=inp), st)
    return next(c for c in st.checks if c["check"] == "told_where_next")


def test_a_waypoint_on_the_surveyors_seat_passes(tmp_path):
    c = told(world(tmp_path, offer=("Rift Surveyor", 3552, 112, 5334)))
    assert c["verdict"] == "PASS" and "npc_main_rift_surveyor" in c["evidence"]


def test_the_league_waypoint_after_gym_8_fails(tmp_path):
    # the state before 2026-10-06: the badge offered the League, which turns the player back until the finale
    c = told(world(tmp_path, offer=("Pokemon League", 3694, 88, 2430)))
    assert c["verdict"] == "FAIL" and "Pokemon League" in c["evidence"]


def test_no_waypoint_at_all_fails(tmp_path):
    assert told(world(tmp_path))["verdict"] == "FAIL"


def test_a_waypoint_left_behind_when_the_actor_moves_fails(tmp_path):
    c = told(world(tmp_path, offer=("Rift Surveyor", 3552, 112, 5334), seat=[3738, 86, 5082]))
    assert c["verdict"] == "FAIL"


def test_no_conversation_moving_the_stage_fails_and_says_so(tmp_path):
    c = told(world(tmp_path, offer=("Rift Surveyor", 3552, 112, 5334), wired=False))
    assert c["verdict"] == "FAIL" and "rift_crisis_pending" in c["evidence"]


def test_an_unbuilt_progression_pack_is_not_modelled(tmp_path):
    inp = world(tmp_path, offer=("Rift Surveyor", 3552, 112, 5334))
    inp.unbuilt["cobblers_progression"] = "data mode"
    assert told(inp)["verdict"] == "NOT_MODELLED"


def test_flag_offer_reads_only_tellraw_lines(tmp_path):
    packs = tmp_path / "packs"
    fn = packs / "cobblers_progression" / "data" / "cobblers" / "function" / "flag" / "x" / "granted.mcfunction"
    write(fn, "# " + share("Old", 1, 2, 3) + "\n")
    assert W.flag_offer(packs, "x")[0] is None
    write(fn, share("New", 4, 5, 6) + "\n")
    assert W.flag_offer(packs, "x")[0] == ("New", 4, 6)
