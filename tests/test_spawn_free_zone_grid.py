"""Spawn-free zone boxes (data/spawn_suppression.json) are on the 8-block grid and hold what they say they hold.

Written by the test author, not by the session that moved the League box.

What is asserted: every zone box is [x0, z0, x1, z1] with x0 and z0 multiples of 8 and x1 + 1, z1 + 1 multiples of 8,
the grid tools/suppress_inherited_spawns.py merge_boxes refuses anything off (the League box at 3776/2504 stopped
`reapply.py install` on 2026-09-25); merge_boxes accepts the real zones together with the route boxes, and still
refuses the old off-grid League box (so the grid test is about the rule the tool enforces); the League zone holds
the League's lot (data/rift_league_tunnel.json lot.box) with a margin; each gym zone holds the gym its "why" names,
footprint computed here from data/placements.json position, size and rotation (tools/place_town.rotate) with the 2
blocks its "why" promises.

Not covered, and it needs a running server: that nothing spawns inside a zone in game (the suppression pack and the
compiled pools are what the server reads; tests/test_spawn_free_zones.py covers the compiled pools offline).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import place_town  # noqa: E402
import suppress_inherited_spawns as SIS  # noqa: E402

DOC = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))
ZONES = DOC["spawn_free_zones"]
PLACEMENTS = {p["id"]: p for p in json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]}
GRID = 8


# Without it the zone list could be emptied and every per-zone test below would pass on nothing.
def test_there_are_zones_and_the_league_is_one():
    assert len(ZONES) >= 9
    assert "league_precinct" in {z["id"] for z in ZONES}


# Without it an off-grid box reaches merge_boxes, which raises, and `reapply.py install` stops before any pack is
# installed (the League box at x1 3776 / z1 2504, 2026-09-25).
@pytest.mark.parametrize("zone", ZONES, ids=[z["id"] for z in ZONES])
def test_a_zone_box_is_on_the_8_block_grid(zone):
    x0, z0, x1, z1 = zone["box"]
    assert x0 < x1 and z0 < z1, zone["box"]
    assert x0 % GRID == 0 and z0 % GRID == 0, zone["box"]
    assert (x1 + 1) % GRID == 0 and (z1 + 1) % GRID == 0, zone["box"]


# Without it the grid rule above could drift from the tool's: this is the call install makes, on the real zones.
def test_merge_boxes_accepts_every_zone_and_refuses_the_old_league_box():
    boxes = [(z["box"][0], z["box"][2], z["box"][1], z["box"][3]) for z in ZONES]
    assert SIS.merge_boxes(boxes)
    with pytest.raises(SystemExit):
        SIS.merge_boxes([(3616, 3776, 2352, 2511)])
    with pytest.raises(SystemExit):
        SIS.merge_boxes([(3616, 3783, 2352, 2504)])


def _holds(box, x0, z0, x1, z1):
    return box[0] <= x0 and box[1] <= z0 and box[2] >= x1 and box[3] >= z1


# Without it the League box is re-snapped to the grid by shrinking it, and the champion's lot is left open to spawns.
def test_the_league_zone_holds_the_leagues_lot_with_its_margin():
    lot = json.loads((ROOT / "data" / "rift_league_tunnel.json").read_text(encoding="utf-8"))["lot"]["box"]
    box = next(z["box"] for z in ZONES if z["id"] == "league_precinct")
    x0, z0, x1, z1 = lot
    assert _holds(box, x0, z0, x1, z1), (box, lot)
    # the stated margin is 16 blocks, snapped out to the grid: never less than 16 on any side
    assert _holds(box, x0 - 16, z0 - 16, x1 + 16, z1 + 16), (box, lot)


def _footprint(p):
    """(x0, z0, x1, z1) of a corner-anchored template placement, from its position, size and rotation."""
    if p.get("mirror", "none") != "none" or p.get("anchor_mode", "corner") != "corner":
        pytest.skip("%s is mirrored or not corner-anchored: this footprint model does not cover it" % p["id"])
    sx, _sy, sz = p["size"]
    xs, zs = [], []
    for tx in (0, sx - 1):
        for tz in (0, sz - 1):
            rx, rz = place_town.rotate(tx, tz, p.get("rotation", "none"))
            xs.append(p["position"]["x"] + rx)
            zs.append(p["position"]["z"] + rz)
    return min(xs), min(zs), max(xs), max(zs)


GYM_ZONES = [z for z in ZONES if z["id"].startswith("gym_")]


# Without it a gym zone is left where the gym used to be (as the League's was until 2026-09-23), and a wild Pokemon
# wanders into a leader battle.
@pytest.mark.parametrize("zone", GYM_ZONES, ids=[z["id"] for z in GYM_ZONES])
def test_a_gym_zone_holds_the_gym_its_why_names_with_two_blocks_round_it(zone):
    m = re.search(r"\((\w+), as placed\)", zone["why"])
    assert m, "the zone's why does not name its building"
    p = PLACEMENTS.get(m.group(1))
    assert p is not None, "%s names %s, which data/placements.json does not place" % (zone["id"], m.group(1))
    x0, z0, x1, z1 = _footprint(p)
    assert _holds(zone["box"], x0 - 2, z0 - 2, x1 + 2, z1 + 2), (zone["box"], (x0, z0, x1, z1))


# Without it a gym zone could be deleted and the parametrised check above would simply run once fewer.
def test_there_are_eight_gym_zones():
    assert len(GYM_ZONES) == 8
