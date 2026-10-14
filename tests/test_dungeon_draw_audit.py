"""The INDEPENDENT audit of the dungeon draw (tools/dungeon_draw_audit.py): tests of the audit itself, then the audit run on the
real generator and the real data.

Three kinds, and what each can and cannot show:

  * FIXTURE tests (seconds, no heightmap, no build): the audit's checkers run on a small synthetic world with answers worked out
    by hand in the test, so a checker that only works on the real surface fails here. They test the audit, not the draw.
  * REAL-DATA tests (seconds, need the heightmap): the audit's siting rules over data/dungeon_rips.json.
  * SIMULATOR tests (marked slow: the dungeon pack takes about five minutes to build): the generated draw functions run on
    tests/pocket_sim.py, then the same run against MUTATED COPIES OF tools/dungeon.py (data/ untouched), each of which the
    audit must fail. A mutation of the record would move the expectation and the output together and prove nothing.

Not covered, and not coverable here (testing.md: validity is not runtime behaviour): that `random value` and
`scoreboard players operation %=` behave on a server as the simulator models them, that the click advancement reaches its door
function in game, and that the oval stands where the siting says. Those are EXP-034's shape and a staging boot.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon_draw_audit as A  # noqa: E402


# ------------------------------------------------------------------------------------------------- the spec's expectations


def test_the_spec_table_counts_per_band_come_out_of_the_roster():
    # DUNGEON_DRAW.md 2.2 states the table by hand: bands 1-3 draw 5, band 4 draws 6, band 5 draws 11, band 6 draws 13.
    # Without this, the expectation the scenarios use could drift from the owner's approved table unseen.
    built = {d["id"] for d in json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))["dungeons"]}
    expect = A.roster_expectations(built_ids=built)
    counts = [len(A.eligible(b, set(A.ALL_FLAGS), expect)) for b in range(1, 7)]
    assert counts == [5, 5, 5, 6, 11, 13], counts


def test_eligibility_is_first_band_at_or_under_the_band_and_the_gate_held():
    # a hand-built roster: a floor of 4 behind gym 6, a floor of 5 behind gym 8. `<` for `<=` here is the slip the audit exists for
    exp = {"a": (1, None), "b": (4, "g6"), "c": (5, "g8")}
    assert A.eligible(1, {"g6", "g8"}, exp) == {"a"}
    assert A.eligible(4, set(), exp) == {"a"}
    assert A.eligible(4, {"g6"}, exp) == {"a", "b"}
    assert A.eligible(3, {"g6"}, exp) == {"a"}, "the gate does not lower the floor"
    assert A.eligible(5, {"g6"}, exp) == {"a", "b"}, "gym 6's flag is not gym 8's"
    assert A.eligible(5, {"g8"}, exp) == {"a", "c"}


def test_roster_prose_gates_are_read_to_their_flag_and_an_unreadable_one_fails_closed():
    # the roster writes 'gym8_cleared (proposed, ...)'; a gate the parser cannot read must stop the audit, not become "no gate"
    doc = {"dungeons": [{"id": "x", "first_band": 5, "gate": "gym8_cleared (proposed, Q13 OPEN)"},
                        {"id": "y", "first_band": 1, "gate": None},
                        {"id": "z", "first_band": 6, "gate": "champion_cleared (DUNGEONS.md 10)"}]}
    assert A.roster_expectations(doc) == {"x": (5, "gym8_cleared"), "y": (1, None), "z": (6, "champion_cleared")}
    with pytest.raises(ValueError):
        A.roster_expectations({"dungeons": [{"id": "w", "first_band": 5, "gate": "all eight badges"}]})


def test_every_band_of_the_real_roster_has_a_candidate():
    # DUNGEON_DRAW.md 3: "every band has at least one candidate"; with no candidate the draw falls back to the first dungeon
    built = {d["id"] for d in json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))["dungeons"]}
    expect = A.roster_expectations(built_ids=built)
    for b in range(1, 7):
        assert A.eligible(b, set(A.ALL_FLAGS), expect), b
    assert A.eligible(1, set(), expect) == {i for i, (fb, fl) in expect.items() if fb == 1 and fl is None}


def test_the_record_carries_the_rosters_first_band_and_gate_per_dungeon():
    # the owner took the roster's first bands and gates as written (DUNGEON_DRAW.md 5); a dungeon whose record drifted is drawn wrong
    doc = json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))
    expect = A.roster_expectations(built_ids={d["id"] for d in doc["dungeons"]})
    for d in doc["dungeons"]:
        fb, flag = expect[d["id"]]
        assert d["first_band"] == fb, d["id"]
        assert d["gate_flag"] == ("cobblers:flag/%s" % flag if flag else None), d["id"]
    assert doc["engine"]["lockout_ticks"] == 72000, "the spec's lockout is one hour of uptime"


# ------------------------------------------------------------------------------------------------- the checkers, on a synthetic world


SEA = 62
WORLD_LAKES = [(80, [[(200, 200), (220, 200), (220, 220), (200, 220)]])]


def flat(x, z):
    """The synthetic ground: y70 everywhere, a pit to y50 for x in 100..110 (under the sea), a lake bed at y70 under a level-80 lake."""
    return 50 if 100 <= x <= 110 else 70


def rip(x0, z, y=71, region="sq", kind="region", rid="rip_t"):
    return {"id": rid, "kind": kind, "region": region, "frame": {"x0": x0, "x1": x0 + 4, "z": z, "y": y, "height": 4},
            "click": [x0 + 2, y, z + 1], "outside": [x0 + 2.5, y, z + 3.5, 0]}


SQUARE = {"sq": [[(0, 0), (1000, 0), (1000, 1000), (0, 1000)]]}


def check(rips, points=(), boxes=(), regions=SQUARE, ground=flat):
    return A.siting_problems(rips, ground, SEA, WORLD_LAKES, list(points), list(boxes), regions)


def test_the_footprint_is_the_plane_the_click_and_the_exit_point():
    # x0=500..504, z=500; the exit point is z 503.5, so its block is 503: the footprint is x500..504 z500..503
    assert A.footprint(rip(500, 500)) == (500, 500, 504, 503)


def test_a_clean_rip_on_dry_ground_passes_and_a_wet_one_is_named():
    assert check([rip(500, 500)]) == []
    wet = check([rip(100, 500, y=51)])           # ground y50 is under the sea at y62
    assert len(wet) == 1 and "under sea" in wet[0], wet
    lake = check([rip(204, 204)])                # ground y70 under a level-80 lake basin
    assert any("a lake" in p for p in lake), lake
    # a column above its lake's level is dry: the same basin with the level at 70 holds no water over y70 ground
    assert A.siting_problems([rip(204, 204)], flat, SEA, [(70, WORLD_LAKES[0][1])], [], [], SQUARE) == []


def test_the_plane_stands_on_the_ground_plus_one():
    assert any("frame.y" in p for p in check([rip(500, 500, y=80)]))
    assert check([rip(500, 500, y=71)]) == []


def test_clearance_is_measured_from_the_footprints_edge_and_thirty_passes():
    # footprint (500,500)-(504,503). A point 30.0 away along x passes; 29 fails; diagonals are Euclidean
    assert check([rip(500, 500)], points=[(534.0, 501.0, "f")]) == []
    near = check([rip(500, 500)], points=[(533.0, 501.0, "f")])
    assert len(near) == 1 and "29.0" in near[0], near
    assert check([rip(500, 500)], points=[(534.0, 507.0, "f")]) == []          # hypot(30, 4) = 30.27
    assert len(check([rip(500, 500)], points=[(529.0, 507.0, "f")])) == 1       # hypot(25, 4) = 25.3
    assert len(check([rip(500, 500)], points=[(502.0, 501.0, "f")])) == 1       # on the rip itself: distance 0


def test_a_trail_rip_still_in_the_standing_list_is_a_problem_and_exempt_from_nothing():
    # the owner retired the 13 trail rips on 2026-10-13: a test_trail record in `rips` means the retirement did not happen, and it
    # gets no clearance exemption any more. Without this the old exemption could quietly outlive the decision.
    t = rip(500, 500, kind="test_trail", y=71)
    got = check([t])
    assert len(got) == 1 and "test_trail" in got[0], got
    near = check([t], points=[(505.0, 500.0, "f")])
    assert any("blocks from the footprint" in p for p in near), "no clearance exemption: " + str(near)
    assert any("under sea" in p for p in check([rip(100, 500, y=51, kind="test_trail")]))


def test_a_precinct_that_the_footprint_touches_is_named_and_a_block_of_air_is_not():
    assert check([rip(500, 500)], boxes=[(505, 500, 600, 600, "town x")]) == [], "one block clear of the town"
    hit = check([rip(500, 500)], boxes=[(504, 500, 600, 600, "town x")])
    assert len(hit) == 1 and "town x" in hit[0], hit


def test_a_footprint_corner_outside_its_region_is_named_and_a_missing_region_too():
    tight = {"sq": [[(0, 0), (503, 0), (503, 1000), (0, 1000)]]}      # x 500..504 sticks out past x503
    assert any("outside region" in p for p in check([rip(500, 500)], regions=tight))
    assert any("not in data/regions.json" in p for p in check([rip(500, 500, region=None)]))


ZONES = {"zones": {"z2": {"name": "the deep", "pass": {"kind": "badges", "threshold": 8, "advancements": ["f/g1", "f/g8"]}, "boxes": [[490, 498, 510, 505]]},
                   "z3": {"name": "free", "pass": None, "boxes": [[0, 0, 1000, 1000]]}}}
REACH = {"zone": "z2", "zone_name": "the deep", "kind": "badges", "threshold": 8, "advancements": ["f/g1", "f/g8"]}


def test_which_gated_zone_a_footprint_stands_in_is_decided_by_the_box_edge():
    # footprint of rip(x0, z) is x0..x0+4, z..z+3; the box is x490..510 z498..505. An ungated zone (pass None) never counts
    assert A.gated_zones_of(rip(500, 500), ZONES) == ["z2"]
    assert A.gated_zones_of(rip(511, 500), ZONES) == [], "x511 is one block clear of the box"
    assert A.gated_zones_of(rip(510, 500), ZONES) == ["z2"], "x510 touches the box edge"
    assert A.gated_zones_of(rip(500, 520), ZONES) == [], "south of the box"
    assert A.gated_zones_of(rip(500, 500), {"zones": {"z3": ZONES["zones"]["z3"]}}) == []


def test_a_gated_rip_that_declares_its_zone_as_the_zones_file_has_it_is_allowed():
    # the owner, 2026-10-13: 'every area in game should be capable of spawning a rift, so leave it even if its gated'.
    # Without this the audit would go on failing a rip the owner decided to keep.
    inside = dict(rip(500, 500, rid="rip_in"), reachable_after=dict(REACH))
    assert A.gated_zone_problems([inside], ZONES) == []
    assert A.gated_zone_problems([rip(511, 500, rid="rip_out")], ZONES) == [], "outside every gated zone and claiming nothing"


def test_a_gated_rip_with_no_declaration_or_a_wrong_one_is_named():
    undeclared = A.gated_zone_problems([rip(500, 500, rid="rip_in")], ZONES)
    assert len(undeclared) == 1 and "rip_in" in undeclared[0] and "no reachable_after" in undeclared[0], undeclared
    for field, wrong in (("zone", "z3"), ("zone_name", "elsewhere"), ("kind", "caught"), ("threshold", 7), ("advancements", ["f/g1"])):
        bad = dict(rip(500, 500, rid="rip_in"), reachable_after=dict(REACH, **{field: wrong}))
        assert A.gated_zone_problems([bad], ZONES), "a wrong %s was accepted" % field


def test_a_rip_outside_every_gated_zone_that_claims_one_is_named():
    # a stale claim promises the player a wait that does not exist
    stale = dict(rip(511, 500, rid="rip_out"), reachable_after=dict(REACH))
    got = A.gated_zone_problems([stale], ZONES)
    assert len(got) == 1 and "rip_out" in got[0] and "no gated rift zone" in got[0], got


def test_the_retired_rips_positions_are_compared_by_dungeon_not_by_order():
    old = {"dungeons": [{"id": "a", "rip": {"frame": {"x0": 1}, "click": [1, 2, 3], "outside": [1.5, 2, 3.5, 0]}},
                        {"id": "b", "rip": {"frame": {"x0": 9}, "click": [9, 2, 3], "outside": [9.5, 2, 3.5, 0]}}]}

    def new(a_x, b_x):
        return [{"id": "rip_b", "kind": "test_trail", "legacy_dungeon": "b", "frame": {"x0": b_x}, "click": [b_x, 2, 3], "outside": [b_x + .5, 2, 3.5, 0]},
                {"id": "rip_a", "kind": "test_trail", "legacy_dungeon": "a", "frame": {"x0": a_x}, "click": [a_x, 2, 3], "outside": [a_x + .5, 2, 3.5, 0]}]
    assert A.old_test_rip_positions(old, new(1, 9)) == []
    moved = A.old_test_rip_positions(old, new(2, 9))
    assert moved and all("retired rip for a" in p for p in moved), moved
    assert any("gone" in p for p in A.old_test_rip_positions(old, new(1, 9)[:1]))


# ------------------------------------------------------------------------------------------------- a rip in every dry region


def heights(x0, z0, x1, z1):
    """flat() as the (z, x) array Ground.box returns."""
    import numpy as np
    return np.array([[flat(x, z) for x in range(x0, x1 + 1)] for z in range(z0, z1 + 1)])


def test_dry_columns_are_counted_on_the_global_grid_inside_the_polygon_and_above_the_sea():
    # step 10 samples x,z in multiples of 10. a: square (4,4)-(46,46) holds x,z in {10,20,30,40} = 16 columns, all y70 (dry).
    # b: (95,5)-(125,45) holds x in {100,110,120} (ground 50, 50, 70) and z in {10..40} = 4: only x120 is above the sea.
    # c: x95..115 holds x 100 and 110, both y50: under the sea, so a region with none (the Jungle Isle's shape).
    regions = {"a": [[(4, 4), (46, 4), (46, 46), (4, 46)]], "b": [[(95, 5), (125, 5), (125, 45), (95, 45)]],
               "c": [[(95, 5), (115, 5), (115, 45), (95, 45)]]}
    got = A.regions_dry_columns(heights, SEA, regions, step=10, size=1000)
    assert got == {"a": 16, "b": 4, "c": 0}, got


def test_a_region_of_two_rings_counts_the_columns_of_both():
    # two rings are a union (regions.json lists islands as polygons): the second ring's columns count
    regions = {"two": [[(4, 4), (26, 4), (26, 26), (4, 26)], [(34, 4), (56, 4), (56, 26), (34, 26)]]}
    assert A.regions_dry_columns(heights, SEA, regions, step=10, size=1000) == {"two": 4 + 4}     # x,z in {10,20} and {40,50}


def test_a_dry_region_without_a_rip_is_named_and_a_drowned_one_without_is_not():
    # the decision: every region with dry ground has a rip. Jungle Isle (no dry column) has none and is not a fault
    dry = {"north": 5, "south": 3, "drowned": 0}
    rips = [{"id": "r1", "region": "north"}]
    got = A.region_rip_problems(rips, dry)
    assert len(got) == 1 and "south" in got[0], got
    assert A.region_rip_problems(rips + [{"id": "r2", "region": "south"}], dry) == []


# ------------------------------------------------------------------------------------------------- the retired rips, on a synthetic pack


THEMES = {"t": {"hull": {"floor": "minecraft:stone", "wall": "minecraft:cobblestone"}}}


def retired_rip():
    """A 3-wide, 2-high plane at x10..12 z20 from y70, a click at (11, 70, 21); its patch is the two cells (11,21) and (10,21) at y69.
    Theme t: floor stone, wall cobblestone. (11,21) was coarse dirt (stone is put back to it); (10,21) was cobblestone, which is the
    theme's own wall, so that cell needs no line."""
    return {"id": "rip_old", "kind": "test_trail", "legacy_dungeon": "d", "scorch_theme": "t", "region": "sq",
            "frame": {"x0": 10, "x1": 12, "z": 20, "y": 70, "height": 2}, "click": [11, 70, 21], "outside": [11.5, 70, 23.5, 0],
            "restore": {"10": ["minecraft:dirt", "minecraft:air"], "11": ["minecraft:air", "minecraft:air"], "12": ["minecraft:air", "minecraft:air"]},
            "retired": {"ground": {"11,21": "minecraft:coarse_dirt", "10,21": "minecraft:cobblestone"}}}


GOOD_RETIRE = ["# retire", "setblock 10 70 20 minecraft:dirt", "setblock 10 71 20 minecraft:air", "fill 11 70 20 12 71 20 minecraft:air",
               "execute if block 11 69 21 minecraft:stone run setblock 11 69 21 minecraft:coarse_dirt"]


def retire_pack(lines=GOOD_RETIRE, extra=None):
    files = {A.RIPS_DIR + "retire.mcfunction": "# top\nexecute in minecraft:overworld run function cobblers:dungeons/rips/retire_old\n",
             "data/cobblers/function/dungeons/rips/retire_old.mcfunction": "\n".join(lines)}
    files.update(extra or {})
    return files


def test_a_retire_function_that_restores_the_plane_and_the_patch_passes():
    assert A.retire_pack_problems(retire_pack(), [retired_rip()], THEMES) == []


def test_a_retire_function_with_a_wrong_plane_cell_is_named():
    lines = [l.replace("setblock 10 70 20 minecraft:dirt", "setblock 10 70 20 minecraft:stone") for l in GOOD_RETIRE]
    got = A.retire_pack_problems(retire_pack(lines), [retired_rip()], THEMES)
    assert len(got) == 1 and "(10, 70, 20)" in got[0], got


def test_a_retire_function_that_leaves_a_plane_cell_untouched_is_named():
    got = A.retire_pack_problems(retire_pack([l for l in GOOD_RETIRE if "fill" not in l]), [retired_rip()], THEMES)
    assert len(got) == 4 and all("rip.restore says minecraft:air" in p for p in got), got       # x11..12 at y70 and y71


def test_a_retire_function_that_skips_the_patch_is_named():
    got = A.retire_pack_problems(retire_pack([l for l in GOOD_RETIRE if "execute" not in l]), [retired_rip()], THEMES)
    assert len(got) == 1 and "(11, 69, 21)" in got[0] and "never put back" in got[0], got


def test_a_patch_cell_already_holding_the_themes_own_block_needs_no_line():
    # (10,21) is cobblestone, the theme's wall: a line for it is not required (but an unrequired one is not an error either)
    assert A.retire_pack_problems(retire_pack(), [retired_rip()], THEMES) == []
    extra = GOOD_RETIRE + ["execute if block 10 69 21 minecraft:stone run setblock 10 69 21 minecraft:cobblestone"]
    assert A.retire_pack_problems(retire_pack(extra), [retired_rip()], THEMES) == []


def test_a_patch_put_back_unconditionally_is_named_so_a_reapply_cannot_overwrite_new_ground():
    lines = GOOD_RETIRE[:-1] + ["setblock 11 69 21 minecraft:coarse_dirt"]
    got = A.retire_pack_problems(retire_pack(lines), [retired_rip()], THEMES)
    assert any("outside its plane" in p for p in got) and any("never put back" in p for p in got), got


def test_a_patch_put_back_only_where_a_foreign_block_stands_is_named():
    lines = GOOD_RETIRE[:-1] + ["execute if block 11 69 21 minecraft:dirt run setblock 11 69 21 minecraft:coarse_dirt"]
    got = A.retire_pack_problems(retire_pack(lines), [retired_rip()], THEMES)
    assert len(got) == 1 and "none of the theme's blocks" in got[0], got


def test_a_patch_put_back_to_the_wrong_block_is_named():
    lines = GOOD_RETIRE[:-1] + ["execute if block 11 69 21 minecraft:stone run setblock 11 69 21 minecraft:dirt"]
    got = A.retire_pack_problems(retire_pack(lines), [retired_rip()], THEMES)
    assert len(got) == 1 and "retired.ground says minecraft:coarse_dirt" in got[0], got


def test_a_retire_that_writes_a_cell_a_standing_rips_blocks_function_writes_is_named():
    got = A.retire_pack_problems(retire_pack(extra={A.RIPS_DIR + "blocks_new.mcfunction": "setblock 11 69 21 minecraft:grass_block"}),
                                 [retired_rip()], THEMES)
    assert len(got) == 1 and "standing rip" in got[0], got


def test_a_missing_retire_entry_or_a_missing_called_function_is_named():
    assert "nothing to run" in A.retire_pack_problems({}, [retired_rip()], THEMES)[0]
    files = retire_pack()
    del files["data/cobblers/function/dungeons/rips/retire_old.mcfunction"]
    got = A.retire_pack_problems(files, [retired_rip()], THEMES)
    assert any("not in the pack" in p for p in got), got


def test_a_retire_function_may_not_hold_a_command_the_audit_cannot_read():
    got = A.retire_pack_problems(retire_pack(GOOD_RETIRE + ["kill @e[type=minecraft:cow]"]), [retired_rip()], THEMES)
    assert len(got) == 1 and "does not read" in got[0], got


SWEEP = ("forceload add 8 18 16 26\n"
         "execute store result score #n s run kill @e[type=minecraft:interaction,tag=dg.rip_old]\n"
         "execute store result score #n s run kill @e[type=minecraft:item_display,tag=dg.rip_old]\n")
STANDING = 'summon minecraft:interaction 99.5 64 99.5 {width:3.0f,Tags:["dg.rip","dg.rip_new","dg.rip_other"]}\n'


def sweep_pack(sweep=SWEEP, standing=STANDING):
    return {A.RIPS_DIR + "entities_retired_look.mcfunction": sweep, A.RIPS_DIR + "entities.mcfunction": standing}


def test_the_entity_sweep_covers_the_click_and_kills_both_entities_of_each_retired_rip():
    assert A.retire_sweep_problems(sweep_pack(), [retired_rip()]) == []
    assert "not in the pack" in A.retire_sweep_problems({}, [retired_rip()])[0]
    far = A.retire_sweep_problems(sweep_pack(SWEEP.replace("8 18 16 26", "80 18 90 26")), [retired_rip()])
    assert len(far) == 1 and "click (11, 21)" in far[0], far
    half = A.retire_sweep_problems(sweep_pack(SWEEP.replace("item_display", "marker")), [retired_rip()])
    assert any("oval tags" in p for p in half), half


def test_the_entity_sweep_may_not_kill_a_tag_a_standing_rip_is_summoned_with():
    standing = STANDING.replace("dg.rip_other", "dg.rip_old")
    got = A.retire_sweep_problems(sweep_pack(standing=standing), [retired_rip()])
    assert len(got) == 1 and "standing rip" in got[0] and "dg.rip_old" in got[0], got


def test_a_retired_rip_with_a_click_that_reaches_a_function_or_a_summon_at_its_click_is_named():
    r = retired_rip()
    assert A.retired_click_problems({}, [r], {}) == []
    assert "still reaches" in A.retired_click_problems({}, [r], {"rip_old": "cobblers:dungeons/door/x"})[0]
    files = {A.RIPS_DIR + "entities.mcfunction": 'summon minecraft:interaction 11.5 70 21.5 {Tags:["a"]}'}
    got = A.retired_click_problems(files, [r], {})
    assert len(got) == 1 and "summons an interaction at its click" in got[0], got
    far = {A.RIPS_DIR + "entities.mcfunction": 'summon minecraft:interaction 12.5 70 21.5 {Tags:["a"]}'}
    assert A.retired_click_problems(far, [r], {}) == []


def test_r16dr_runs_the_retire_and_the_sweep_and_r16dg_does_not():
    fn = lambda n: ("fn", "cobblers:dungeons/" + n)
    good = [("R16DG", "shells", [fn("place")]), ("R16DR", "rips", [fn("rips/place"), fn("rips/retire"), fn("rips/entities_retired")])]
    assert A.retire_step_problems(good, [retired_rip()]) == []
    assert A.retire_step_problems(good, []) == [], "nothing retired, nothing to run"
    no_retire = [good[0], ("R16DR", "rips", [fn("rips/place"), fn("rips/entities_retired")])]
    assert any("rips/retire" in p for p in A.retire_step_problems(no_retire, [retired_rip()]))
    no_sweep = [good[0], ("R16DR", "rips", [fn("rips/place"), fn("rips/retire")])]
    assert any("entities_retired" in p for p in A.retire_step_problems(no_sweep, [retired_rip()]))
    wrong_step = [("R16DG", "shells", [fn("rips/retire")]), good[1]]
    assert any("R16DG runs" in p for p in A.retire_step_problems(wrong_step, [retired_rip()]))


def test_the_retired_record_check_names_a_standing_trail_rip_a_shared_click_and_an_overlap():
    standing = rip(500, 500, rid="rip_s")
    old = dict(retired_rip(), id="rip_old")
    assert A.retired_record_problems([standing], [old], ["d"]) == []
    assert any("retired and standing" in p for p in A.retired_record_problems([dict(standing, id="rip_old")], [old], ["d"]))
    assert any("trail rip" in p for p in A.retired_record_problems([dict(standing, kind="test_trail")], [old], ["d"]))
    assert any("click" in p for p in A.retired_record_problems([dict(standing, click=old["click"])], [old], ["d"]))
    near = rip(8, 18, rid="rip_near")      # footprint x8..12 z18..21 touches the retired plane
    assert any("touches standing rip_near" in p for p in A.retired_record_problems([near], [old], ["d"]))
    assert any("dungeons are" in p for p in A.retired_record_problems([standing], [old], ["d", "e"])), "a dungeon whose rip was never retired"


def test_authored_points_reads_xz_dicts_pairs_and_triples_but_not_boxes(tmp_path):
    d = tmp_path / "data"
    (d / "sub").mkdir(parents=True)
    (d / "a.json").write_text(json.dumps({"p": {"x": 10, "z": 20}, "q": [30, 40], "r": [50, 99, 60], "box": [1, 2, 3, 4],
                                          "cc": {"cx": 70, "cz": 80}, "off": [9000, 5]}), encoding="utf-8")
    (d / "sub" / "b.json").write_text(json.dumps({"x": 100, "z": 200}), encoding="utf-8")
    (d / "skip.json").write_text(json.dumps({"x": 1, "z": 1}), encoding="utf-8")
    got = sorted((x, z, f) for x, z, f in A.authored_points(d, skip_files=("data/skip.json",)))
    assert got == [(10.0, 20.0, "data/a.json"), (30.0, 40.0, "data/a.json"), (50.0, 60.0, "data/a.json"),
                   (70.0, 80.0, "data/a.json"), (100.0, 200.0, "data/sub/b.json")]


def test_a_rips_click_function_is_found_by_the_tag_the_advancement_listens_for():
    adv = {"criteria": {"click": {"trigger": "t", "conditions": {"entity": [{"predicate": {"nbt": '{Tags:["tagA"]}'}}]}}},
           "rewards": {"function": "cobblers:dungeons/door/whatever"}}
    files = {"data/cobblers/advancement/dungeons/rip_x.json": json.dumps(adv),
             "data/cobblers/function/dungeons/rips/entities.mcfunction":
                 'summon minecraft:interaction 10.5 64 20.5 {width:3.0f,Tags:["dg.rip","tagA","dg.rip_new"]}\n'
                 'summon minecraft:interaction 99.5 64 99.5 {width:3.0f,Tags:["tagZ"]}\n'}
    rips = [{"id": "r1", "click": [10, 64, 20]}, {"id": "r2", "click": [99, 64, 99]}, {"id": "r3", "click": [1, 1, 1]}]
    assert A.rip_click_functions(files, rips) == {"r1": "cobblers:dungeons/door/whatever"}, "r2's tag has no advancement, r3 has no interaction"


def test_a_rotation_window_must_hold_each_wanted_dungeon_once():
    want = {"a", "b", "c"}
    assert A._permutation_windows(["a", "b", "c", "a", "b", "c", "a"], want) == []
    assert A._permutation_windows(["a", "b", "c", "c", "a", "b"], want) != [], "c twice in a row"
    assert A._permutation_windows(["a", "b", "a", "b", "c"], want) != [], "a returns before c is seen"


def test_every_mutation_targets_exactly_one_spot_of_the_generator_source():
    # a mutation that finds its text twice or not at all is no longer a mutation of the draw: the audit's independence proof
    # would silently go stale when the generator is edited
    src = (ROOT / "tools" / "dungeon.py").read_text(encoding="utf-8")
    for name, m in A.MUTATIONS.items():
        old, new = m["edit"]
        assert src.count(old) == 1, "%s: target occurs %d times" % (name, src.count(old))
        assert old != new, name


def test_a_mutation_whose_target_is_gone_refuses_to_load_and_is_not_loosened(monkeypatch):
    monkeypatch.setitem(A.MUTATIONS, "stale", {"why": "x", "edit": ("this text is nowhere in dungeon.py", "y")})
    with pytest.raises(RuntimeError, match="update the mutation"):
        A.load_module("stale")


def test_a_mutation_counts_as_caught_only_by_a_problem_the_control_did_not_have():
    base = {"a": ["old defect"], "b": []}
    assert A.novel(base, {"a": ["old defect"], "b": []}) == {}, "a defect the real generator already has proves nothing"
    assert A.novel(base, {"a": ["old defect", "new"], "b": []}) == {"a": ["new"]}
    assert A.novel(base, {"a": ["old defect"], "b": ["boom"]}) == {"b": ["boom"]}


# ------------------------------------------------------------------------------------------------- real data, heightmap


def _have_heightmap():
    try:
        import ground as G
        G.load()
        return True
    except Exception:
        return False


needs_heightmap = pytest.mark.skipif(not _have_heightmap(), reason="the canonical heightmap is not reachable (COBBLERS_SOURCE_ROOT / .claude/settings.json)")


@pytest.fixture(scope="module")
def siting():
    out = {}
    return A.run_siting(out), out


def _real_rips():
    doc = json.loads((ROOT / "data" / "dungeon_rips.json").read_text(encoding="utf-8"))
    return doc["rips"], doc.get("retired_rips") or []


@needs_heightmap
def test_the_real_rips_are_dry_clear_of_authored_coordinates_outside_precincts_and_inside_their_region(siting):
    # DUNGEON_DRAW.md 2.6, measured from tools/ground.py round(h) and data/*.json read by the audit, not by tools/dungeon_rips.py.
    # 20 = the dry regions (21 in data/regions.json less the drowned Jungle Isle), all of kind region; the 13 trail rips are retired.
    # The whole verdict is asserted, not a subset: the gated, dry-region and retired checks are inside `problems` too.
    problems, out = siting
    assert out["siting"]["rips"] == 20 and out["siting"]["region_rips"] == 20 and out["siting"]["retired_rips"] == 13, out["siting"]
    assert problems == []


@needs_heightmap
@needs_heightmap
def test_every_region_with_dry_ground_has_a_rip_and_only_the_drowned_jungle_isle_has_none(siting):
    # the owner, 2026-10-13: 'every area in game should be capable of spawning a rift'. The dry set is measured from the heightmap
    # here, not read from the rips: a region that lost its rip, or a heightmap that stopped finding land, both fail this.
    _, out = siting
    rips, _retired = _real_rips()
    regs = A.region_polygons()
    import ground as G
    dry = A.regions_dry_columns(G.load().box, A.water_world()[0], regs)
    assert [rid for rid, n in dry.items() if n == 0] == ["jungle_isle"], dry
    assert out["siting"]["regions"] == 21 and out["siting"]["regions_with_dry_ground"] == 20
    assert {r["region"] for r in rips} == set(regs) - {"jungle_isle"}
    assert any("jungle_isle has no dry ground" in n for n in out["siting_notes"])


def test_the_gated_rip_check_is_not_vacuous_on_the_real_zones():
    # rip_the_rift stands in zone z2 (badges 8), read from data/rift_zones.json here. A reader that found no zone boxes would pass
    # every rip and the check would prove nothing; and a rip that moved out of the zone must drop its claim.
    rips, _ = _real_rips()
    zones = json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))
    gated = {r["id"]: A.gated_zones_of(r, zones) for r in rips if A.gated_zones_of(r, zones)}
    assert gated == {"rip_the_rift": ["z2"]}, gated
    z2 = zones["zones"]["z2"]["pass"]
    assert (z2["kind"], z2["threshold"]) == ("badges", 8)
    declared = {r["id"]: r["reachable_after"] for r in rips if r.get("reachable_after")}
    assert list(declared) == ["rip_the_rift"] and declared["rip_the_rift"]["zone"] == "z2"
    assert A.gated_zone_problems(rips, zones) == []


def test_the_retired_records_are_exactly_the_13_dungeons_rips_and_none_stands():
    rips, retired = _real_rips()
    dungeons = [d["id"] for d in json.loads((ROOT / "data" / "dungeons.json").read_text(encoding="utf-8"))["dungeons"]]
    assert len(retired) == 13 and len(dungeons) == 13
    assert A.retired_record_problems(rips, retired, dungeons) == []


@needs_heightmap
def test_the_siting_audit_reads_a_real_number_of_authored_points(siting):
    # an audit that read no points would pass every clearance: the walk over data/ must find tens of thousands
    _, out = siting
    assert out["siting"]["points_read"] > 20000, out["siting"]


@needs_heightmap
def test_the_cli_writes_its_full_result_to_the_file_and_prints_one_verdict_line(capsys, tmp_path):
    # the output contract: a long result never lands in the transcript (CLAUDE.md "Context cost"), one line does
    out = tmp_path / "result.json"
    rc = A.main(["--only", "siting", "--out", str(out)])
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1 and lines[0].split(":")[0] in ("PASS", "FAIL"), lines
    assert (rc == 0) == lines[0].startswith("PASS")
    got = json.loads(out.read_text(encoding="utf-8"))
    assert {"siting", "siting_problems", "siting_notes"} <= set(got)


@needs_heightmap
def test_the_siting_tool_refuses_sites_made_to_break_one_rule_each():
    # tools/dungeon_rips.py is handed a too-near coordinate, a town beside the plane, a foreign region, a neighbour rip and a sea
    # floor, with the spec's distances (30, 300). Without this, a siting tool that approves everything passes `check` forever.
    assert A.sc_siting_tool_rejects_sites_that_break_a_rule(A.load_rips_module(None)) == []


@needs_heightmap
@pytest.mark.parametrize("mutation", sorted(A.RIPS_MUTATIONS))
def test_the_audit_fails_when_the_siting_tool_is_mutated(mutation):
    # independence for the siting tool: tools/dungeon_rips.py edited at one spot, data/ untouched, and the audit must object
    got = A.sc_siting_tool_rejects_sites_that_break_a_rule(A.load_rips_module(mutation))
    assert got, "MISSED: %s (%s)" % (mutation, A.RIPS_MUTATIONS[mutation]["why"])


def test_every_siting_mutation_targets_exactly_one_spot_of_the_tool_source():
    src = (ROOT / "tools" / "dungeon_rips.py").read_text(encoding="utf-8")
    for name, m in A.RIPS_MUTATIONS.items():
        assert src.count(m["edit"][0]) == 1, name


def test_the_retired_records_still_hold_the_plane_the_owner_played():
    # git show 6249332e: data/dungeons.json carried each dungeon's rip. The retire function restores the RECORD's plane, so the
    # record must still be where the owner saw the rip; otherwise the retire would clean the wrong blocks.
    r = subprocess.run(["git", "show", "%s:data/dungeons.json" % A.OLD_TEST_RIPS_COMMIT], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("commit %s is not in this checkout: %s" % (A.OLD_TEST_RIPS_COMMIT, r.stderr.strip()[:120]))
    _, retired = _real_rips()
    assert A.old_test_rip_positions(json.loads(r.stdout), retired) == []


# ------------------------------------------------------------------------------------------------- the generator's retire, no full build


def _retire_files(mod, retired):
    """The retire functions as `mod` emits them, without the five-minute build: rips/retire's calls and rip_retire_lines per rip.
    The wiring text mirrors tools/dungeon.py's build() (rips/retire_<rip_name>); the slow scenario retired_rips_are_taken_out reads
    the real build. What this reads is the line generator, which is where a skipped plane or patch would be."""
    files = {A.RIPS_DIR + "retire.mcfunction": "\n".join(
        ["# top"] + ["execute in minecraft:overworld run function cobblers:dungeons/rips/retire_%s" % mod.rip_name(r) for r in retired])}
    for r in retired:
        files["data/cobblers/function/dungeons/rips/retire_%s.mcfunction" % mod.rip_name(r)] = "\n".join(mod.rip_retire_lines(r))
    return files


def _themes():
    return json.loads((ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8"))["themes"]


def test_the_generators_retire_lines_restore_every_recorded_plane_and_patch():
    # the 13 real retired records, the real tools/dungeon.py line generator, expectations from the records and the theme file
    _, retired = _real_rips()
    got = A.retire_pack_problems(_retire_files(A.load_module(None), retired), retired, _themes())
    assert got == [], got[:3]


@pytest.mark.parametrize("mutation", A.RETIRE_MUTATIONS)
def test_the_retire_check_fails_when_the_generators_retire_lines_are_mutated(mutation):
    # independence: tools/dungeon.py edited at one spot (data/ untouched) and the retire check must object. These three are also in
    # A.MUTATIONS for the slow full-build run; here the same edit meets the checker without the build.
    _, retired = _real_rips()
    got = A.retire_pack_problems(_retire_files(A.load_module(mutation), retired), retired, _themes())
    assert got, "MISSED: %s (%s)" % (mutation, A.MUTATIONS[mutation]["why"])


def test_the_generators_entity_sweep_covers_every_retired_click_and_kills_both_entities():
    import dungeon as D
    _, retired = _real_rips()
    doc = D.load()
    files = {"data/" + fid.replace(":dungeons/", "/function/dungeons/") + ".mcfunction": "\n".join(lines) for fid, lines in D.retire_sweep(doc).items()}
    assert files and all(p.startswith(A.RIPS_DIR + "entities_retired") for p in files), sorted(files)
    assert A.retire_sweep_problems(files, retired) == []


# ------------------------------------------------------------------------------------------------- the simulator (slow)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    got, facts = A.run_draw(A.load_module(None), tmp_path_factory.mktemp("draw_audit"))
    return got, facts


SCENARIO_NAMES = [n for n, _ in A.SCENARIOS] + ["reapply_wires_r16dr", "input_validators"]


@pytest.mark.slow
@pytest.mark.parametrize("scenario", SCENARIO_NAMES)
def test_the_generated_draw_holds_the_specs_property(baseline, scenario):
    # each scenario's docstring and name say the property; its expectations come from the spec and the roster
    got, _ = baseline
    assert "contract_names" not in got, got.get("contract_names")
    assert scenario in got, "scenario did not run"
    assert got[scenario] == []


@pytest.mark.slow
@pytest.mark.parametrize("mutation", sorted(A.MUTATIONS))
def test_the_audit_fails_when_the_generator_is_mutated(baseline, mutation, tmp_path):
    # independence: the generator (tools/dungeon.py source) is edited at one spot, data/ untouched, and the audit must object
    # with a problem the unmutated run did not have. A mutation that passes is a property the audit does not hold.
    got, _ = A.run_draw(A.load_module(mutation), tmp_path)
    assert A.novel(baseline[0], got), "MISSED: %s (%s)" % (mutation, A.MUTATIONS[mutation]["why"])
