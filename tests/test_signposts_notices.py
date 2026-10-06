"""Notices: signs that explain rather than name (data/signposts.json notices, tools/signposts.py; the owner, 2026-10-06:
"Victory Road and the Rift finale are explained in the world"; docs/world-building/POST_GYM8_DIRECTION.md).

Two notices: one on the Rift floor before the Sink Gate naming the Compact's HQ (CRITICAL_PATH_WALK_2 item 6), and one
on the Deep's north face beside Victory Road's mouth. Where each stands is checked against other files than the
notice's own record: the Deep's pit from tools/rift_deep.model() (the canonical heightmap and the traced region), the
mouth from data/vr_caves.json, the posts from posts() itself.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import signposts as S  # noqa: E402

CFG = json.loads((ROOT / "data" / "signposts.json").read_text(encoding="utf-8"))
NOTICES = {n["id"]: n for n in CFG["notices"]}


def _posts():
    import ground as G
    from elder_trees import painted_water
    S.SUBNAMES.update(S._subnames())
    g = G.Ground(S.env_source_root())
    return S.posts(g, painted_water(g.heights, g.world))


@pytest.fixture(scope="module")
def posts():
    try:
        return {p["id"]: p for p in _posts()}
    except (FileNotFoundError, OSError) as e:
        pytest.skip("posts() needs the heightmap and build/paint: %s" % str(e)[:160])


def test_every_notice_is_an_expected_post():
    ids = S.expected_post_ids()
    for nid in NOTICES:
        assert "notice_%s" % nid in ids


def test_every_notice_line_fits_a_sign_as_authored():
    for n in NOTICES.values():
        for side in ("front", "back"):
            ls = S.notice_lines(n, side)
            assert len(ls) == 4 and all(len(t) <= 15 for t in ls), (n["id"], side, ls)
        assert S.notice_lines(n, "front") == (n["front"] + [""] * 4)[:4]


def test_a_line_too_long_for_a_sign_is_refused_not_wrapped():
    n = copy.deepcopy(NOTICES["deep_lip"])
    n["front"][1] = "Compact Headquarters"
    with pytest.raises(SystemExit, match="15 characters"):
        S.notice_lines(n, "front")


def test_a_wall_notice_with_a_back_or_no_facing_is_refused():
    n = copy.deepcopy(NOTICES["vr_mouth"])
    n["back"] = ["behind the wall"]
    with pytest.raises(SystemExit, match="no back"):
        S.notice_lines(n, "back")
    n = copy.deepcopy(NOTICES["vr_mouth"])
    n["wall"]["facing"] = "up"
    with pytest.raises(SystemExit, match="facing"):
        S.notice_lines(n, "front")


def test_a_wall_notice_is_a_wall_sign_with_no_fence():
    p = {"id": "notice_vr_mouth", "x": 3566, "y": 2, "z": 3064, "wall": "south",
         "front": ["VICTORY ROAD", "", "", ""], "back": ["", "", "", ""]}
    nbt = S.sign_nbt(p, "spruce")
    assert nbt.startswith("minecraft:spruce_wall_sign[facing=south]{front_text:"), nbt


def test_the_hq_notice_names_the_hq_and_the_way_down():
    words = " ".join(NOTICES["deep_lip"]["front"]).lower()
    for w in ("deep", "compact hq", "sink gate", "top ring", "west"):
        assert w in words, (w, words)


def test_the_hq_notice_stands_on_the_rift_floor_outside_the_pit_and_off_every_post(posts):
    import rift_deep as R
    m = R.model(S.env_source_root())
    X0, Z0, X1, Z1 = m["box"]
    p = posts["notice_deep_lip"]
    if X0 <= p["x"] <= X1 and Z0 <= p["z"] <= Z1:
        assert m["ring"][p["z"] - Z0, p["x"] - X0] < 0, "the notice stands inside the Deep's pit: %s" % p
    others = [q for q in posts.values() if q["id"] != p["id"]
              and abs(q["x"] - p["x"]) <= S.NOTICE_GAP and abs(q["z"] - p["z"]) <= S.NOTICE_GAP]
    assert not others, others
    # before the Sink Gate on the way in: within 100 blocks of its exit (data/deep_city.json's gate, the plan's
    # exit is relayed in the record's why and not re-read here), on the trunk side
    assert abs(p["x"] - 3695) + abs(p["z"] - 3394) < 120, p


def test_the_victory_road_notice_hangs_on_the_north_face_beside_the_mouth():
    vr = json.loads((ROOT / "data" / "vr_caves.json").read_text(encoding="utf-8"))
    mx, my, mz = vr["mouth"]["at"]
    w = NOTICES["vr_mouth"]["wall"]
    x, y, z = w["at"]
    assert vr["mouth"]["toward"] == "north" and w["facing"] == "south"   # the caves run north; the sign faces the pit
    assert z == mz, "on the face's line, as the mouth is"
    assert 3 < abs(x - mx) <= 8, "beside the tunnel (|x - mouth| <= 3 is the tunnel itself), not in it"
    assert y == my + 1, "head height for a player standing at the mouth's level"
    assert "VICTORY ROAD" in NOTICES["vr_mouth"]["front"] and "the League" in NOTICES["vr_mouth"]["front"]


def test_the_wall_notice_is_where_its_record_says(posts):
    p = posts["notice_vr_mouth"]
    assert [p["x"], p["y"], p["z"]] == NOTICES["vr_mouth"]["wall"]["at"] and p["wall"] == "south"
