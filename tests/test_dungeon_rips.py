"""The dungeon rips as data (data/dungeon_rips.json, tools/dungeon_rips.py): the BUILDER's own tests.

A rip is a place, not a dungeon (docs/mechanics/DUNGEON_DRAW.md 2.6, built 2026-10-13). What each test holds is said where
it is. The heightmap-dependent checks skip where the canonical heightmap is not present (a worktree without the source
tree); every one of them reads tools/ground.py, never a world. The independent audit of the draw is another agent's.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_rips as DRP  # noqa: E402

RIPS_DOC = DRP.load()
RIPS = RIPS_DOC["rips"]
DUNGEONS = json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))
ROSTER = {d["id"]: d for d in json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))["dungeons"]}
REGIONS = [r["id"] for r in json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["regions"]]

# The thirteen test rips stand where the owner played them (2026-10-13: "keep them as general rips at their current
# positions"). Their plane's x0 and z, copied from data/dungeons.json at 6249332e (before the rips left the records).
TRAIL = {"night_shift": (1350, 4117), "jungle": (1380, 4118), "flooded_ruin": (1400, 4120), "ash_bell": (1448, 4118),
         "soul_ossuary": (1523, 4118), "moth_cathedral": (1473, 4118), "dragonspiral": (1604, 4117),
         "field_of_swords": (1625, 4118), "warped_lab": (1500, 4118), "crucible": (1421, 4118), "starfall": (1673, 4118),
         "street": (1552, 4118), "patriarch": (1575, 4118)}
# A region with no dry ground at all cannot hold a rip. Measured 2026-10-13 on the heightmap: every column of the jungle
# isle's polygon is at or under y61, sea level y62 (the water shape removed the isle; data/water_shape.json jungle_isle_bank).
NO_DRY_GROUND = {"jungle_isle"}


@pytest.fixture(scope="module")
def ground():
    try:
        import ground as G
        return G.load()
    except Exception as ex:                      # the source tree is not mounted here
        pytest.skip("no canonical heightmap: %s" % ex)


def test_no_dungeon_record_carries_a_rip_any_more():
    # breaks if a rip is put back into a dungeon: the draw would then have two owners for where a dungeon opens
    assert all("rip" not in d for d in DUNGEONS["dungeons"])


def test_the_thirteen_test_rips_stand_where_they_stood_and_keep_their_dungeons_ground():
    by = {r["legacy_dungeon"]: r for r in RIPS if r.get("legacy_dungeon")}
    assert set(by) == set(TRAIL)
    themes = {d["id"]: d["theme"] for d in DUNGEONS["dungeons"]}
    for did, (x0, z) in TRAIL.items():
        r = by[did]
        assert (r["frame"]["x0"], r["frame"]["z"]) == (x0, z), did
        assert r["kind"] == "test_trail" and r["scorch_theme"] == themes[did], did
    # they are the first thirteen, in the dungeons' order: dg.rip numbers are append-only
    assert [r["legacy_dungeon"] for r in RIPS[:13]] == [d["id"] for d in DUNGEONS["dungeons"]]


def test_every_region_with_dry_ground_has_a_rip_and_the_rest_say_why():
    have = {r["region"] for r in RIPS}
    missing = [r for r in REGIONS if r not in have]
    assert set(missing) == NO_DRY_GROUND, missing


def test_the_region_rips_are_one_per_region_and_never_on_the_trail():
    reg = [r for r in RIPS if r["kind"] == "region"]
    assert len(reg) == len({r["region"] for r in reg}) and len(reg) >= 15
    trail = [r for r in RIPS if r["kind"] == "test_trail"]
    for r in reg:
        assert r["id"].startswith("rip_") and r["scorch_theme"] not in ("nether_wastes", "crimson_forest", "warped_forest",
                                                                       "soul_sand_valley", "basalt_deltas"), r["id"]
        for t in trail:
            assert math.hypot(r["click"][0] - t["click"][0], r["click"][2] - t["click"][2]) > 300, (r["id"], t["id"])


def test_the_records_and_the_engine_agree_there_is_nothing_wrong_with_the_rips():
    doc = D.load()
    assert D.rip_problems(doc) == [] and D.draw_problems(doc) == []
    assert DRP.problems(RIPS_DOC) == []


def test_every_region_rip_is_sited_by_every_rule_on_the_heightmap(ground):
    # tools/dungeon_rips.py check: flat 9 x 7 window, dry, 30 from every authored coordinate, 60 from the road, outside
    # every spawn-free zone and town footprint, inside its region, 300 from the other region rips. Breaks if a rip moves
    # onto sloping, wet or occupied ground, or if a new authored point lands within 30 blocks of one.
    assert DRP.problems(RIPS_DOC, ground) == []


def test_a_region_rips_plane_and_restore_are_re_measured_from_the_heightmap(ground):
    # rip.restore is what the plane held before (air above the ground); a drift between it and the heightmap would leave
    # a block in the plane or take one from under it
    for r in RIPS:
        if r["kind"] == "region":
            assert D.rip_restore_measured(r, ground) == r["restore"], r["id"]
            f = r["frame"]
            assert f["y"] == ground(DRP.mid_x(f), f["z"] + 1) + 1, r["id"]


def test_the_trail_rips_keep_their_measured_restore(ground):
    import route1_old_mine as MINE
    mine = MINE.build(ground)
    for r in RIPS:
        if r["kind"] == "test_trail":
            assert D.rip_restore_measured(r, ground, mine) == r["restore"], r["id"]


def test_first_band_and_gate_flag_are_the_rosters_for_every_dungeon():
    # data/dungeon_prize_roster.json is the design's proposal; data/dungeons.json is what the engine reads. They must not
    # drift: a dungeon drawn below the roster's floor would have a prize pool the roster did not give that band.
    import re
    for d in DUNGEONS["dungeons"]:
        ro = ROSTER[d["id"]]
        assert d["first_band"] == ro["first_band"], d["id"]
        m = re.match(r"^(gym\d_cleared|champion_cleared)", ro["gate"] or "")
        assert d["gate_flag"] == ("cobblers:flag/" + m.group(1) if m else None), d["id"]
    progression = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    flags = {f["id"] for f in progression["flags"]}
    for d in DUNGEONS["dungeons"]:
        if d["gate_flag"]:
            assert d["gate_flag"].split("/", 1)[1] in flags, d["id"]    # the advancement tools/progression_pack.py emits


def test_the_presence_probes_in_world_probes_are_the_ones_the_tool_writes():
    # data/world_probes.json dungeon_rips is generated (python tools/dungeon_rips.py probes --write): an edit by hand, or a
    # rip added without re-writing, leaves the world check short of a rip. The Night Shift's three stay in dungeon_night_shift.
    places = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]
    assert places["dungeon_rips"] == DRP.probes(RIPS_DOC)["dungeon_rips"]
    assert len(places["dungeon_rips"]) == 3 * (len(RIPS) - 1)


def test_every_band_has_two_ungated_dungeons_so_the_draw_rotates_and_never_strands_a_player():
    # a band with one open dungeon would repeat it every click, and a player locked out of it (or finding it full) would
    # have nothing to be drawn. Band 1-3 are the five early dungeons; the gated late ones only ever add to a band
    for b in DUNGEONS["engine"]["bands"]:
        open_ = [d["id"] for d in DUNGEONS["dungeons"] if d["first_band"] <= b["band"] and not d["gate_flag"]]
        assert len(open_) >= 2, (b["band"], open_)
        if b["band"] <= 3:
            assert len(open_) == 5 and all(ROSTER[i]["rare_pool_by_band"].get(str(b["band"])) for i in open_), (b["band"], open_)


def test_every_test_rips_legacy_dungeon_is_a_dungeon():
    assert {r["legacy_dungeon"] for r in RIPS if r.get("legacy_dungeon")} == {d["id"] for d in DUNGEONS["dungeons"]}


def test_a_rip_that_floats_or_leaves_its_region_is_found():
    # the check bites: move a region rip's plane one block and the rules name it (the mutation is on the record the
    # tool reads, so this tests the CHECK; the generator is tested by the independent audit)
    import copy
    bad = copy.deepcopy(RIPS_DOC)
    r = next(x for x in bad["rips"] if x["kind"] == "region")
    r["click"][0] += 1
    assert any("click" in p for p in DRP.problems(bad))
