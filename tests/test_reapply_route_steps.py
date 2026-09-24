"""tools/reapply.py: the Routes 1-3 steps (R12 event sites, R17 props, scene NPCs and route trainers) and their packs.

Written by the test author, not by the session that added the steps.

What is asserted: R12 runs after the signposts (R15), R17 after R12 and after the towns (R8, which build the Route 1
mansion the Gastly props sit in); R12 runs every function cobblers_route_events lists, in its order; R17 places every
scene's props (with their count), every scene NPC (conversation, position, class) and every trainer seat (id,
position, yaw), derived here from data/scenes.json, data/dialogue.json and data/route_trainers.json, not from
reapply's own helpers; the three new packs are installed on the server; cobblers_trainers is excluded with a reason;
and the fail-closed coverage check reports the event-site pack or the scene pack when its step is gone.

steps() reads each generated pack's index.txt, so the order and coverage tests SKIP when build/datapacks does not
hold them (run `python tools/reapply.py prepare` first); that skip is not a pass.

Not covered, and it needs a server: that R17's RCON commands place the props, NPCs and trainers (summon_persistent,
spawnnpcat), that a re-run leaves one of each, and that the NPC classes and trainer data are loaded after the restart.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reapply  # noqa: E402

NEEDS_INDEX = (("cobblers_rift", "rift"), ("cobblers_rift_biome", "rift"), ("cobblers_league_tunnel", "league_tunnel"),
               ("cobblers_deep", "deep"), ("cobblers_vr_caves", "vr_caves"), ("cobblers_route_events", "route_events"))
SCENES = json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))["scenes"]
CONVS = {c["id"]: c for c in json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))["conversations"]}
SEATS = json.loads((ROOT / "data" / "route_trainers.json").read_text(encoding="utf-8"))["trainers"]


@pytest.fixture(scope="module")
def steps():
    if not reapply.PACKS.is_dir():
        pytest.skip("no build/datapacks: the generated packs are not built in this checkout")
    missing = [p for p, f in NEEDS_INDEX
               if not (reapply.PACKS / p / "data" / "cobblers" / "function" / f / "index.txt").is_file()]
    if missing:
        pytest.skip("steps() reads index.txt of packs not built here: %s (python tools/reapply.py prepare)" % missing)
    return reapply.steps()


def _at(steps, sid):
    ids = [s[0] for s in steps]
    assert sid in ids, "no step %s in %s" % (sid, ids)
    return ids.index(sid)


def _acts(steps, sid, kind):
    return [v for k, v in steps[_at(steps, sid)][2] if k == kind]


# Without it the event sites go in before the signposts and a donor's air margin (as with Sabrina's store and the
# Route 7 post) erases them, or the props and trainers are placed before the sites and the mansion they stand in.
@pytest.mark.parametrize("before,after", [("R15", "R12"), ("R12", "R17"), ("R8", "R17")])
def test_route_event_steps_run_in_order(steps, before, after):
    assert _at(steps, before) < _at(steps, after)


# Without it R12 runs a subset of the sites, none (an empty index), or runs them out of the order the pack wrote.
def test_r12_runs_every_route_events_function_the_pack_lists_in_its_order(steps):
    listed = reapply.indexed("cobblers_route_events", "route_events")
    assert listed, "cobblers_route_events lists no functions: the test would pass on nothing"
    assert steps[_at(steps, "R12")][2] == [("fn", "cobblers:route_events/%s" % f) for f in listed]
    base = reapply.PACKS / "cobblers_route_events" / "data" / "cobblers" / "function" / "route_events"
    assert all((base / ("%s.mcfunction" % f)).is_file() for f in listed)


# Without it a scene's interaction boxes are never placed after a re-export (every prop click is gone), or R17 counts
# the wrong number of boxes and passes a partial placement.
def test_r17_places_every_scenes_props_with_their_count(steps):
    got = {sid: (box, n) for sid, box, n in _acts(steps, "R17", "props")}
    want = {s["id"]: len(s["props"]) for s in SCENES if s.get("props")}
    assert want, "no scene has props: the rule was never exercised"
    assert {sid: n for sid, (_box, n) in got.items()} == want
    for s in SCENES:
        if s.get("props"):
            x0, z0, x1, z1 = got[s["id"]][0]
            assert all(x0 <= p["at"][0] <= x1 + 1 and z0 <= p["at"][2] <= z1 + 1 for p in s["props"]), s["id"]


# Without it a scene NPC is missing after a re-export, stands somewhere else, or is spawned with another class.
def test_r17_places_every_scene_npc_at_its_position_with_its_class(steps):
    want = [(n["conversation"], tuple(n["at"]), "cobblers:%s" % CONVS[n["conversation"]]["npc_id"])
            for s in SCENES for n in s.get("npcs") or []]
    assert len(want) >= 8
    assert sorted(_acts(steps, "R17", "npc")) == sorted(want)


# Without it a route trainer is not placed after a re-export, or at a seat other than the recorded one.
def test_r17_places_every_trainer_at_its_seat(steps):
    want = [(t["id"], tuple(t["seat"]), t["yaw"]) for t in SEATS]
    assert len(want) == 13
    assert sorted(_acts(steps, "R17", "trainer")) == sorted(want)


# Without it the new packs are built but never installed, and the sites' functions, the scene runtime or the trainer
# data are missing from the running game.
@pytest.mark.parametrize("pack", ["cobblers_route_events", "cobblers_scenes", "cobblers_trainers"])
def test_the_route_packs_are_installed_on_the_server(pack):
    assert pack in reapply.SERVER_PACKS


# Without it the trainers' pack (functions run only as advancement rewards) falls into the fail-closed check and
# `prepare` stops, or it is excluded with no reason written down.
def test_the_trainers_pack_is_excluded_with_a_reason():
    assert str(reapply.EXCLUDED.get("cobblers_trainers", "")).strip()
    assert "cobblers_route_events" not in reapply.EXCLUDED and "cobblers_scenes" not in reapply.EXCLUDED


# Without it R12 or R17 could be deleted and the re-apply would still report green while the sites or the props are
# gone after the next export.
@pytest.mark.parametrize("step,pack", [("R12", "cobblers_route_events"), ("R17", "cobblers_scenes")])
def test_uncovered_reports_the_pack_when_its_step_is_gone(steps, step, pack):
    if pack not in reapply.function_packs():
        pytest.skip("%s is not built in build/datapacks" % pack)
    assert not [b for b in reapply.uncovered(steps) if b.startswith(pack + " ")]
    without = [s for s in steps if s[0] != step]
    assert any(b.startswith(pack + " ") for b in reapply.uncovered(without))
