"""The dungeon rips as data (data/dungeon_rips.json, tools/dungeon_rips.py): the BUILDER's own tests.

A rip is a place, not a dungeon (docs/mechanics/DUNGEON_DRAW.md 2.6, built 2026-10-13). What each test holds is said where
it is. The heightmap-dependent checks skip where the canonical heightmap is not present (a worktree without the source
tree); every one of them reads tools/ground.py, never a world. The independent audit of the draw is another agent's.

2026-10-13, later: the owner retired the 13 rips on the old mine's trail ("the rips near old mine have to go") and said every
region should be able to hold a rift, gated or not. The trail rips are under `retired_rips`; Pallet Fields and Shrew Lakes
have rips of their own; a rip behind a gate records it (`reachable_after`) and is not a problem.
"""
from __future__ import annotations

import copy
import json
import math
import re
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
RETIRED = RIPS_DOC["retired_rips"]
DUNGEONS = json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))
ROSTER = {d["id"]: d for d in json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))["dungeons"]}
REGIONS = [r["id"] for r in json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["regions"]]

# The thirteen test rips stood where the owner played them, and were RETIRED on 2026-10-13. Their plane's x0 and z, copied
# from data/dungeons.json at 6249332e (before the rips left the records).
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


@pytest.fixture(scope="module")
def mine(ground):
    # the old mine's own build over the heightmap: slow (about a minute), so once for the module
    import route1_old_mine as MINE
    return MINE.build(ground)


def test_no_dungeon_record_carries_a_rip_any_more():
    # breaks if a rip is put back into a dungeon: the draw would then have two owners for where a dungeon opens
    assert all("rip" not in d for d in DUNGEONS["dungeons"])


def test_the_thirteen_test_rips_are_retired_not_standing_and_still_on_record():
    # the owner, 2026-10-13: "the rips near old mine have to go". Breaks if one comes back into `rips` (the draw would put a
    # click back on the trail), or if a record is deleted instead of kept (CLAUDE.md: hand-authored work is kept)
    assert not [r["id"] for r in RIPS if r["kind"] == "test_trail" or r.get("legacy_dungeon")]
    by = {r["legacy_dungeon"]: r for r in RETIRED}
    assert set(by) == set(TRAIL) and len(RETIRED) == 13
    themes = {d["id"]: d["theme"] for d in DUNGEONS["dungeons"]}
    for did, (x0, z) in TRAIL.items():
        r = by[did]
        assert (r["frame"]["x0"], r["frame"]["z"]) == (x0, z), did
        assert r["kind"] == "test_trail" and r["scorch_theme"] == themes[did], did
        assert r["retired"]["on"] == "2026-10-13" and "rips near old mine" in r["retired"]["by"], did
    assert [r["legacy_dungeon"] for r in RETIRED] == [d["id"] for d in DUNGEONS["dungeons"]]


def test_every_retired_rip_gives_its_ground_back_cell_for_cell_and_says_how_it_knows():
    # retired.ground is one block per patch cell (rip_retire_lines reads it by "x,z"); a missing cell would raise at build, an
    # extra one would be dead data. The basis says MEASURED or ASSUMED, so an assumed block is never mistaken for a read one
    for r in RETIRED:
        cells = {"%d,%d" % (x, z) for x, _y, z, _b in D.rip_scorch_cells(r)}
        assert set(r["retired"]["ground"]) == cells, r["id"]
        assert r["retired"]["ground_basis"].split()[0] in ("MEASURED", "ASSUMED,"), r["id"]
    assert D.rip_problems(D.load()) == []


def test_the_night_shifts_notch_floor_is_what_the_old_mines_own_build_laid(mine):
    # the one retired patch whose ground IS known: the notch floor, coarse dirt at feet - 1 (tools/route1_old_mine.py). The
    # replay is the mine's own build over the patch's cells, not the record, so a changed floor breaks this
    ns = RETIRED[0]
    cells = {(x, y, z): b for x, y, z, b in D.rip_scorch_cells(ns)}
    state = {}
    for ln in mine:
        t = ln.split()
        if not t or t[0] not in ("fill", "setblock"):
            continue
        if t[0] == "setblock":
            c = (int(t[1]), int(t[2]), int(t[3]))
            if c in cells:
                state[c] = t[4]
            continue
        a = [int(v) for v in t[1:7]]
        for c in cells:
            if all(min(a[k], a[k + 3]) <= c[k] <= max(a[k], a[k + 3]) for k in range(3)):
                state[c] = t[7]
    assert len(state) == len(cells)
    for (x, _y, z), blk in state.items():
        assert ns["retired"]["ground"]["%d,%d" % (x, z)] == blk, (x, z)


def test_the_retire_functions_touch_only_the_retired_rips_and_the_sweep_kills_only_their_tags():
    # a retired rip's functions put its OWN plane and patch back; if one wrote into a standing rip's window, or the sweep killed
    # a standing rip's tag, a re-apply would erase a rip the world should keep
    doc = D.load()
    fns = D.functions(doc)
    stand = list(D.rips(doc))
    for r in D.retired_rips(doc):
        f = r["frame"]
        for ln in fns["rips/retire_%s" % D.rip_name(r)]:
            m = re.search(r"(?:fill|setblock) (-?\d+) (-?\d+) (-?\d+)", ln)
            if m:
                x, z = int(m.group(1)), int(m.group(3))
                assert f["x0"] <= x <= f["x1"] and f["z"] <= z <= f["z"] + 2, (r["id"], ln)
        for s in stand:
            assert D.rip_tag(s) != D.rip_tag(r)
    sweep = "\n".join(D.retire_sweep(doc)["cobblers:dungeons/rips/entities_retired_look"])
    assert all("tag=%s]" % D.rip_tag(r) in sweep for r in D.retired_rips(doc))
    assert not any("tag=%s]" % D.rip_tag(s) in sweep for s in stand)
    assert D.build_only("cobblers:dungeons/rips/retire") and D.build_only("cobblers:dungeons/rips/retire_ns")
    assert not D.build_only("cobblers:dungeons/rips/entities_retired_look")      # the sweep is scheduled: it must stay in the runtime pack


def test_r16dr_runs_the_retire_blocks_and_the_sweep_before_it_summons_the_standing_rips():
    # a re-apply that never ran the retire functions would leave the trail rips in the world (the owner, 2026-10-13: "have to
    # go"); and the count the chain reads back must stay the standing rips only
    steps = dict((s[0], s[2]) for s in D.reapply_steps(D.load()))["R16DR"]
    fn = [a[1] for a in steps if a[0] == "fn"]
    assert fn[:3] == ["cobblers:dungeons/rips/place", "cobblers:dungeons/rips/retire", "cobblers:dungeons/rips/entities_retired"]
    assert ("check", ("chunk_look", D.RIP_HOLDER, len(RIPS), "dungeon rips")) in steps


def test_the_way_out_of_a_player_with_no_rip_score_is_the_first_standing_rip():
    # the 13 rips that "stood for" a dungeon are gone, so the legacy leave-by-the-dungeons-rip branch is too
    out = "\n".join(D.functions(D.load())["m/out"])
    assert "stood for its dungeon" not in out
    x, y, z, _yaw = RIPS[0]["outside"]
    assert "unless score @s dg.rip matches 1.. in minecraft:overworld run tp @s %s %s %s" % (D.fmt(float(x)), y, D.fmt(float(z))) in out


def test_every_region_with_dry_ground_has_a_rip_and_the_rest_say_why():
    have = {r["region"] for r in RIPS}
    missing = [r for r in REGIONS if r not in have]
    assert set(missing) == NO_DRY_GROUND, missing


def test_pallet_fields_and_shrew_lakes_have_rips_of_their_own_now_the_trail_rips_are_gone():
    # the trail rips stood in for these two regions; the owner, 2026-10-13: "every area in game should be capable of spawning a
    # rift". Breaks if either goes without a region rip of its own
    own = {r["region"] for r in RIPS if r["kind"] == "region"}
    assert {"pallet_fields", "shrew_lakes"} <= own
    assert set(REGIONS) - own == NO_DRY_GROUND


def test_the_region_rips_are_one_per_region_and_never_back_on_the_old_mines_trail():
    reg = [r for r in RIPS if r["kind"] == "region"]
    assert len(reg) == len({r["region"] for r in reg}) == len(RIPS) and len(reg) >= 15
    for r in reg:
        assert r["id"].startswith("rip_") and r["scorch_theme"] not in ("nether_wastes", "crimson_forest", "warped_forest",
                                                                       "soul_sand_valley", "basalt_deltas"), r["id"]
        for t in RETIRED:       # the owner took these away: no new rip is put within 300 blocks of where they stood
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
        assert D.rip_restore_measured(r, ground) == r["restore"], r["id"]
        f = r["frame"]
        assert f["y"] == ground(DRP.mid_x(f), f["z"] + 1) + 1, r["id"]


def test_the_retired_rips_keep_their_measured_restore(ground, mine):
    # rip.restore is how a retired rip's plane is put back: it must still be what the heightmap and the old mine's build say
    for r in RETIRED:
        assert D.rip_restore_measured(r, ground, mine) == r["restore"], r["id"]


def test_first_band_and_gate_flag_are_the_rosters_for_every_dungeon():
    # data/dungeon_prize_roster.json is the design's proposal; data/dungeons.json is what the engine reads. They must not
    # drift: a dungeon drawn below the roster's floor would have a prize pool the roster did not give that band.
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
    # data/world_probes.json dungeon_rips is generated (python tools/dungeon_rips.py probes --write): an edit by hand, or a rip
    # added or retired without re-writing, leaves the world check short. Three a standing rip and one more for the oval's model
    # value; four a retired one (no interaction, no oval, the ground back, the plane back)
    places = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]
    assert places["dungeon_rips"] == DRP.probes(RIPS_DOC)["dungeon_rips"]
    assert len(places["dungeon_rips"]) == 3 * len(RIPS) + 1 + 4 * len(RETIRED)
    gone = [p for p in places["dungeon_rips"] if "RETIRED" in p["what"] and "entity" in p]
    assert len(gone) == 2 * len(RETIRED) and all(p["count"] == 0 for p in gone)
    # nothing expects a rip where one was retired: the Night Shift place carries no probe of its old rip
    assert not [p for p in places["dungeon_night_shift"] if "dg.rip_ns" in p.get("entity", "")]


def test_every_band_has_two_ungated_dungeons_so_the_draw_rotates_and_never_strands_a_player():
    # a band with one open dungeon would repeat it every click, and a player locked out of it (or finding it full) would
    # have nothing to be drawn. Band 1-3 are the five early dungeons; the gated late ones only ever add to a band
    for b in DUNGEONS["engine"]["bands"]:
        open_ = [d["id"] for d in DUNGEONS["dungeons"] if d["first_band"] <= b["band"] and not d["gate_flag"]]
        assert len(open_) >= 2, (b["band"], open_)
        if b["band"] <= 3:
            assert len(open_) == 5 and all(ROSTER[i]["rare_pool_by_band"].get(str(b["band"])) for i in open_), (b["band"], open_)


def test_every_retired_rips_legacy_dungeon_is_a_dungeon():
    assert {r["legacy_dungeon"] for r in RETIRED} == {d["id"] for d in DUNGEONS["dungeons"]}


def test_a_gated_rip_is_recorded_as_information_and_the_check_does_not_fail_it():
    # the owner, 2026-10-13: "leave it even if its gated". rip_the_rift stands in Rift zone z2 (8 badges); its record says so,
    # and problems() accepts it. A record that disagrees with data/rift_zones.json is the problem, not the gate
    rift = next(r for r in RIPS if r["id"] == "rip_the_rift")
    g = rift["reachable_after"]
    assert (g["zone"], g["kind"], g["threshold"]) == ("z2", "badges", 8) and len(g["advancements"]) == 8
    assert DRP.problems(RIPS_DOC) == []
    assert "reachable_after" not in next(r for r in RIPS if r["id"] == "rip_viltri_woods")
    stale = copy.deepcopy(RIPS_DOC)
    next(r for r in stale["rips"] if r["id"] == "rip_the_rift").pop("reachable_after")
    assert any("reachable_after" in p for p in DRP.problems(stale))
    stale = copy.deepcopy(RIPS_DOC)
    next(r for r in stale["rips"] if r["id"] == "rip_viltri_woods")["reachable_after"] = g
    assert any("reachable_after" in p for p in DRP.problems(stale))


def test_a_rip_that_floats_or_leaves_its_region_is_found():
    # the check bites: move a region rip's plane one block and the rules name it (the mutation is on the record the
    # tool reads, so this tests the CHECK; the generator is tested by the independent audit)
    bad = copy.deepcopy(RIPS_DOC)
    r = next(x for x in bad["rips"] if x["kind"] == "region")
    r["click"][0] += 1
    assert any("click" in p for p in DRP.problems(bad))
