"""A seated NPC never stands inside a block another generator writes.

Route 3's Vessu Ranger (route_03_trainer_05, seat (1980, 134, 1602), tools/route_trainers.py) stood INSIDE the
route_03_misty_to_surge_transition_4 signpost (tools/signposts.py, R15 `cobblers:signs/place`): two generators, each
correct on its own, wrote the same cell (found 2026-10-04 by tools/npc_spot_sweep.py). The post yields: a seat is
chosen, a post moves along the road at no cost (signposts.seat_clash).

The seats here are read from their owners (route_trainers.placements, npc_seats.placements), not from
signposts.npc_seats; the post cells are read from the emitted function when it is built, else from posts().
The last check is the general one: every seat the apply places, against every pack's writes, replayed in apply order
(tools/npc_spot_sweep.py); it needs the prepared build and is skipped without it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import npc_seats as NS  # noqa: E402
import route_trainers as RT  # noqa: E402
import signposts as S  # noqa: E402

SIGNS_FN = ROOT / "build" / "datapacks" / "cobblers_signs" / "data" / "cobblers" / "function" / "signs" / "place.mcfunction"


def seats():
    out = [(tid, tuple(int(v) for v in at)) for tid, at, _yaw in RT.placements()]
    out += [(cid, tuple(int(v) for v in at)) for cid, at, _cls, _yaw in NS.placements()]
    return out


def body_cells(seat_list):
    """{(x, y, z): id}: the feet and head cell of every seat."""
    return {(x, y + dy, z): sid for sid, (x, y, z) in seat_list for dy in (0, 1)}


def test_the_seats_are_there_to_check():
    ids = {sid for sid, _ in seats()}
    assert "route_03_trainer_05" in ids and len(ids) >= 50, len(ids)


def test_a_post_in_or_against_a_seat_clashes_and_one_a_level_away_does_not():
    s = [("t", (100, 70, 200))]
    assert S.seat_clash(100, 70, 200, s) == "t"
    assert S.seat_clash(101, 70, 199, s) == "t"            # against it
    assert S.seat_clash(102, 70, 200, s) is None
    assert S.seat_clash(100, 70 + S.SEAT_REACH_Y + 1, 200, s) is None


def test_the_post_seat_skips_a_cell_a_seat_holds():
    # the seat loop walks the road and takes the first dry, clear cell: put a seat on the first one
    class G:
        ox = oz = 0

        def __call__(self, x, z):
            return 63

    import numpy as np
    wet = np.zeros((400, 400), dtype=bool)
    stand_in = {
        "routes.json": {"routes": [{"id": "r", "from_town": "a", "to_town": "b", "geography": {},
                                    "corridor": {"polyline": [{"x": 100, "z": 100}, {"x": 200, "z": 100}]}}]},
        "towns.json": {"towns": []},
        "placements.json": {"settlements": {}, "placements": []},
        "signposts.json": {"route_labels": {}, "offset_blocks": 4},
    }

    def run(monkey, seat_list):
        monkey.setattr(S, "load", lambda name: stand_in[name])
        monkey.setattr(S, "place_names", lambda: {})
        return {p["id"]: (p["x"], p["z"]) for p in S.posts(G(), wet, seats=seat_list)}

    with pytest.MonkeyPatch.context() as mp:
        free = run(mp, [])
        at = free["r_leaving_a"]
        held = run(mp, [("seat", (at[0], 64, at[1]))])
    assert held["r_leaving_a"] != at
    assert S.seat_clash(held["r_leaving_a"][0], 64, held["r_leaving_a"][1], [("seat", (at[0], 64, at[1]))]) is None
    assert held["r_leaving_b"] == free["r_leaving_b"]      # a post no seat holds does not move


def emitted_post_cells():
    """{(x, y, z): line} every cell the built signs function writes."""
    out = {}
    for line in SIGNS_FN.read_text(encoding="utf-8").splitlines():
        t = line.split()
        if t[:1] == ["fill"] and len(t) >= 8 and all(re.fullmatch(r"-?\d+", v) for v in t[1:7]):
            a = [int(v) for v in t[1:7]]
            for x in range(min(a[0], a[3]), max(a[0], a[3]) + 1):
                for y in range(min(a[1], a[4]), max(a[1], a[4]) + 1):
                    for z in range(min(a[2], a[5]), max(a[2], a[5]) + 1):
                        out[(x, y, z)] = line[:80]
        elif t[:1] == ["setblock"] and len(t) >= 5 and all(re.fullmatch(r"-?\d+", v) for v in t[1:4]):
            out[tuple(int(v) for v in t[1:4])] = line[:80]
    return out


@pytest.mark.skipif(not SIGNS_FN.is_file(), reason="the signs pack is not built (python tools/signposts.py function)")
def test_no_built_post_writes_a_seated_npcs_feet_or_head():
    body = body_cells(seats())
    cells = emitted_post_cells()
    hits = sorted("%s at %s <- %s" % (body[c], list(c), cells[c]) for c in cells if c in body)
    assert not hits, hits


def test_no_post_stands_in_or_against_a_seated_npc():
    import ground as G
    from elder_trees import painted_water
    S.SUBNAMES.update(S._subnames())
    g = G.Ground(S.env_source_root())
    ps = S.posts(g, painted_water(g.heights, g.world))
    body = body_cells(seats())
    bad = []
    for p in ps:
        for y in range(p["y"], p["y"] + 3):       # the fence, the sign, and the air the post clears over them
            if (p["x"], y, p["z"]) in body:
                bad.append("post %s writes %s's cell %s" % (p["id"], body[(p["x"], y, p["z"])], [p["x"], y, p["z"]]))
        near = [sid for sid, (x, y, z) in seats() if abs(x - p["x"]) <= 1 and abs(z - p["z"]) <= 1 and abs(y - p["y"]) <= 2]
        if near:
            bad.append("post %s at %s stands against %s" % (p["id"], [p["x"], p["y"], p["z"]], near))
    assert not bad, bad


def test_every_seat_the_apply_places_is_clear_of_every_packs_writes():
    import npc_spot_sweep as SW
    try:
        res = SW.sweep()
    except (SystemExit, FileNotFoundError) as e:
        pytest.skip("the replay needs the prepared build (python tools/reapply.py prepare): %s" % str(e)[:160])
    bad = ["%s %s at %s: %s" % (s["kind"], s["id"], s["at"], s["detail"]) for s in res["spots"]
           if s["kind"] != "spawner" and s.get("class") == "in_block"]
    assert not bad, bad
