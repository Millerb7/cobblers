"""The six entrance guides: NPCs who offer a shareable Xaero's waypoint to a cave or mine entrance (data/entrance_trails.json
`guides`, wired through data/dialogue.json, quests.json, progression.json, npc_seats.json and npc_looks.json), and the
player site's caves and mines section (tools/entrance_sites.py, docs/player/region-map.html).

What breaks without these tests: a guide whose conversation does not compile (the NPC class never exists, and
tools/npc_seats.py then refuses the seat), a transition that names a function no pack ships (the click does nothing), a
waypoint that points somewhere other than the entrance, a seat on a road or off its plaza, a new quest field the progression
file does not declare, or a site page that names a guide (the public site must not repeat the story files).

NOT COVERED: the dialogue in a running game, the NPC's skin (the texture names are chosen from file names, as the
other looks are), and whether Xaero's accepts the share text in game (its format is read from the mod's source).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_dialogue as CD  # noqa: E402
import entrance_trails as EB  # noqa: E402
import npc_seats as NS  # noqa: E402

DATA = ROOT / "data"
DOC = json.loads((DATA / "entrance_trails.json").read_text(encoding="utf-8"))
QID = "ambient_entrance_guides"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def convs():
    return {c["id"]: c for c in load("dialogue.json")["conversations"]}


@pytest.fixture(scope="module")
def quest():
    return next(q for q in load("quests.json")["quests"] if q["id"] == QID)


def test_each_guide_has_a_conversation_that_belongs_to_its_quest(convs, quest):
    assert len(DOC["guides"]) == 6
    for g in DOC["guides"]:
        c = convs[g["conversation"]]
        assert c["quest_id"] == QID and c["npc_id"] == g["npc"]
        assert g["conversation"] in quest["dialogue_ids"]
        assert c["cursor"]["progression_field"] in quest["progression_field_refs"]


def test_every_conversation_compiles_into_an_npc_class(convs):
    quests = {q["id"]: q for q in load("quests.json")["quests"]}
    fields = {f["id"]: f for f in load("progression.json")["quest_fields"]}
    for g in DOC["guides"]:
        files = CD.compile_conversation(convs[g["conversation"]], quests, fields)
        assert "data/cobblers/npcs/%s.json" % g["npc"] in files
        assert "data/cobblers/dialogues/%s.json" % g["conversation"] in files


def test_each_cursor_field_is_declared_with_the_nodes_the_conversation_uses(convs):
    fields = {f["id"]: f for f in load("progression.json")["quest_fields"]}
    for g in DOC["guides"]:
        c = convs[g["conversation"]]
        f = fields[c["cursor"]["progression_field"]]
        assert f["quest_id"] == QID and f["scope"] == "player" and f["initial"] == c["cursor"]["initial_node"]
        assert set(f["allowed_values"]) == {n["id"] for n in c["nodes"]}


def test_the_mark_transition_runs_the_guides_function_and_moves_the_cursor_to_marked(convs, quest):
    for g in DOC["guides"]:
        key = g["id"][len("guide_"):]
        t = next(t for t in quest["transitions"] if t["id"] == "mark_%s" % key)
        fn = [e for e in t["effects"] if e["kind"] == "function"]
        assert [e["function"] for e in fn] == ["cobblers:guides/%s" % g["id"]]
        cur = [e for e in t["effects"] if e["kind"] == "set_progression"]
        assert [(e["field"], e["value"]) for e in cur] == [(convs[g["conversation"]]["cursor"]["progression_field"], "marked")]


def test_each_guide_is_seated_in_its_town_on_ground_the_seat_rules_accept():
    seats = {s["id"]: s for s in load("npc_seats.json")["seats"]}
    classes = NS.compiled_classes()
    import ground as G
    from terrain import env_source_root
    try:
        g = G.Ground(env_source_root())
    except SystemExit as e:
        pytest.skip("heightmap unavailable: %s" % e)
    mine = [s for s in NS.check(ground=g, classes=classes) if "entrance_guide" in s]
    assert mine == [], mine
    for gd in DOC["guides"]:
        s = seats[gd["npc"]]
        assert s["conversation"] == gd["conversation"] and s["settlement"] == gd["town"]


def test_each_guide_has_a_look_a_class_name_and_a_skin_no_other_look_uses():
    looks = load("npc_looks.json")
    used = {}
    for lid, l in looks["looks"].items():
        used.setdefault(l["texture"], []).append(lid)
    for gd in DOC["guides"]:
        lid = looks["npcs"][gd["npc"]]
        assert lid in looks["looks"], gd["npc"]
        assert used[looks["looks"][lid]["texture"]] == [lid], "the skin is shared with %s" % used[looks["looks"][lid]["texture"]]


def test_the_waypoint_offer_is_the_entrances_share(tmp_path):
    import ground as G
    from terrain import env_source_root
    try:
        g = G.Ground(env_source_root())
    except SystemExit as e:
        pytest.skip("heightmap unavailable: %s" % e)
    ents = EB.entrances()
    for gd in DOC["guides"]:
        cmds, share = EB.guide_commands(gd, ents, g)
        e = ents[gd["goes_to"]]
        m = re.fullmatch(r"xaero-waypoint:([A-Za-z0-9 ]{1,32}):([A-Za-z0-9]{1,3}):(-?\d+):(-?\d+):(-?\d+):(\d+):false:0:Internal-overworld-waypoints", share)
        assert m, share
        assert (int(m.group(3)), int(m.group(4)), int(m.group(5))) == (e["x"], g(e["x"], e["z"]) + 1, e["z"])
        assert cmds[1].startswith("tellraw @s ") and share in cmds[1]


def test_the_marker_names_fit_the_form_the_next_gym_offer_enforces():
    import progression_pack as PP
    for gd in DOC["guides"]:
        assert PP.MARKER_NAME.match(gd["marker"]["name"]) and PP.MARKER_INITIALS.match(gd["marker"]["initials"])
        assert 0 <= gd["marker"]["color"] <= 15


# ---------------------------------------------------------------------------- the player site


def test_the_region_map_lists_every_system_and_marks_every_entrance():
    page = (ROOT / "docs" / "player" / "region-map.html").read_text(encoding="utf-8")
    ents = EB.entrances()
    systems = {}
    for e in ents.values():
        systems.setdefault(e["system"], e["name"])
    assert len(systems) == 6
    for name in systems.values():
        assert name in page, name
    assert page.count('class="pit"') == len(ents)
    assert 'id="L-caves"' in page and 'id="t-caves"' in page
    for e in ents.values():
        assert "x %d, z %d" % (e["x"], e["z"]) in page


def test_the_site_depth_for_a_mine_is_its_first_floor_down_by_the_level_gap():
    import entrance_sites as ES
    import ground as G
    from terrain import env_source_root
    try:
        g = G.Ground(env_source_root())
    except SystemExit as e:
        pytest.skip("heightmap unavailable: %s" % e)
    sites = {s["id"]: s for s in ES.sites(g)}
    # the Old Craters Drift: docs/world-building/MINE_NETWORKS.md measured its levels as "8: 101 down to -11" with the
    # builder's own audit; here they come from the ground at the adit and the data's 16-block gap
    assert sites["mn_craters"]["depth"] == "8 levels, floors from y101 down to y-11"
    assert sites["frostpeak_deeps"]["guide_town"] == "Highwire"
    assert sites["frostpeak_deeps"]["trails"] == [] and len(sites["old_seams"]["trails"]) == 1
    assert len(sites["hollow_reach"]["trails"]) == 2


def test_levels_at_reads_the_areas_whose_boxes_hold_the_point():
    import entrance_sites as ES
    areas = [{"kind": "land", "name": "A", "boxes": [[0, 99, 0, 99]], "rows": [{"lv": [5, 9]}, {"lv": [7, 12]}]},
             {"kind": "sea", "name": "S", "boxes": [[0, 99, 0, 99]], "rows": [{"lv": [1, 90]}]},
             {"kind": "land", "name": "B", "boxes": [[200, 299, 0, 99]], "rows": [{"lv": [30, 40]}]}]
    assert ES.levels_at(areas, 50, 50) == (5, 12, ["A"])
    assert ES.levels_at(areas, 150, 50) is None


def test_the_public_page_names_no_guide_and_no_story_id():
    page = (ROOT / "docs" / "player" / "region-map.html").read_text(encoding="utf-8")
    dialogue = load("dialogue.json")["conversations"]
    for c in dialogue:
        if c["quest_id"] == QID:
            for n in c["nodes"]:
                assert n["text"] not in page
            assert c["npc_name"] not in page and c["npc_id"] not in page
    assert QID not in page
