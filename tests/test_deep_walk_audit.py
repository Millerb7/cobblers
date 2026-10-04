"""tools/deep_walk_audit.py: the Deep walked as a player walks it, through what the packs write.

Written by the test author, not by the session that fixed the Deep's stairs (worktree-agent-a2d56e067168bf7a0). Three
layers:

  rules      the walk's player rules on small synthetic worlds whose answers are counted by hand: a step up needs a
             third clear cell over the step left, a drop of three is walked and four is not, a one-wide gap is jumped
             and a two-wide one is not, a fence and a shut iron door stop him, a plate opens the door, a wall sign does
             not stop him, a lantern at head height does; and the replay's command reader (NBT with spaces, `replace`
             against a tag evaluated on the cells as they stand, `place template` rotated 180)
  the build  the audit over the built packs is clean, the lift tower at door (3544, 3241) is the only one stopped and
             only by its lift, its twin (3664, 3226) climbs, and the sweep finds no other roofed step
  mutation   tools/deep_city.py itself, with a roof put back over step R-3 of the twin tower and nothing in data/
             touched: the audit fails and names that tower, step 14 and the roof cell

The build and mutation layers need the canonical heightmap (COBBLERS_SOURCE_ROOT) and the built packs
(build/datapacks: cobblers_rift, cobblers_deep, cobblers_vr_caves, cobblers_deep_city, cobblers_relic_underground,
cobblers_habitats, cobblers_signs); they SKIP without them, and a skip is not a pass.

Not covered (a running server and a player): lifts, ladders and hatches, how a stair's half-height collision really
feels, the guard admitting at the right stage (tools/relic_underground_audit.py), entity collision, light levels.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import deep_walk_audit as W  # noqa: E402

NEEDED = [p for _s, p, _f in W.REPLAY]
TWIN = (3664, 3226)          # the brief's twin of the lift tower: the tower that must climb on boundary 2
LIFT_TOWER = (3544, 3241)    # the brief's one tower whose roof stays on, over its upper lift


# ------------------------------------------------------------------ synthetic worlds

def corridor(length=15, height=12):
    """A one-wide corridor along x at z=5, walls at z=4 and z=6, rock at and under y0. Box x 0..length-1."""
    w = W.World((0, -4, 0, length - 1, height, 10))
    w.lay_ground(np.zeros((11, length), int))
    w.fill(0, 1, 4, length - 1, height, 4, "minecraft:stone")
    w.fill(0, 1, 6, length - 1, height, 6, "minecraft:stone")
    return w


def walked(w, start=(2, 1, 5), **kw):
    wk = W.Walker(w, **kw)
    return wk, sorted(wk.reached(wk.walk([start])))


def stair(w, roof_over=()):
    """Steps 1..6 at x = 2 + s, y = s (the sixth is the landing at roof height y6); the upper street on x 8..12 at feet
    y7; a roof at y6 over the step columns in roof_over."""
    for s in range(1, 7):
        w.fill(2 + s, s, 5, 2 + s, s, 5, "minecraft:polished_deepslate_stairs[facing=west]")
    w.fill(9, 1, 5, 12, 6, 5, "minecraft:stone")
    for x in roof_over:
        w.fill(x, 6, 5, x, 6, 5, "minecraft:stone")


# Without it, a stair whose roof sits over step R-3 would pass the walk: the defect the Deep shipped with.
def test_a_roof_over_the_step_three_below_the_top_stops_the_climb_and_is_named():
    w = corridor()
    stair(w, roof_over=(3, 4, 5))                  # the roof as the city kept it: off over steps 4 and 5 only
    wk, cells = walked(w)
    assert (10, 7, 5) not in cells
    # by hand: the street (2, 1) and steps 1..3 (feet one over each); step 3 -> 4 needs air at (5, 6), the roof
    assert cells == [(2, 1, 5), (3, 2, 5), (4, 3, 5), (5, 4, 5)]
    ok, why, blk = W._climb(wk, (2, 1, 5), 7, wk.columns_in(0, 0, 14, 10), 0)
    assert not ok and blk == (5, 6, 5) and "step 3 " in why and "minecraft:stone" in why


# Without it, opening the roof over step R-3 (the builder's fix) could still fail the walk and the audit be useless.
def test_with_the_roof_off_over_step_three_below_the_top_the_stair_climbs():
    w = corridor()
    stair(w, roof_over=(3, 4))
    _wk, cells = walked(w)
    # by hand: (2, 1), five steps at feet 2..6, the landing (8, 7) and the street x 9..12 at feet 7 (x 13, 14 border)
    assert cells == [(2, 1, 5), (3, 2, 5), (4, 3, 5), (5, 4, 5), (6, 5, 5), (7, 6, 5)] + [(x, 7, 5) for x in range(8, 13)]


# Without it, the walk could climb walls: a rise of two is not a step.
def test_a_step_up_is_one_block_and_never_two():
    w = corridor()
    w.fill(6, 1, 5, 12, 1, 5, "minecraft:stone")          # rise 1 at x6
    w.fill(9, 2, 5, 12, 3, 5, "minecraft:stone")          # rise 2 more at x9
    _wk, cells = walked(w)
    assert cells == [(x, 1, 5) for x in range(2, 6)] + [(x, 2, 5) for x in range(6, 9)]


# Without it, a fall of any height would count as a way down, and a ring could be "reached" off a cliff.
def test_a_drop_of_three_is_walked_and_a_drop_of_four_is_not():
    for drop, reached in ((3, True), (4, False)):
        w = corridor()
        w.fill(0, 1, 5, 6, drop, 5, "minecraft:stone")    # a ledge, feet at drop + 1, ending at x6
        _wk, cells = walked(w, start=(2, drop + 1, 5))
        assert ((8, 1, 5) in cells) is reached, drop


# Without it, the walk either refuses every gap a player crosses or crosses a gap no player can.
def test_a_gap_of_one_is_jumped_and_a_gap_of_two_is_not():
    for width, reached in ((1, True), (2, False)):
        w = corridor()
        w.fill(6, -4, 5, 5 + width, 0, 5, "minecraft:air")    # a pit to the box's floor
        _wk, cells = walked(w)
        assert ((10, 1, 5) in cells) is reached, width


# Without it, a fence (1.5 high) would be stepped over like a block, and a shut iron door walked through.
def test_a_fence_and_a_shut_iron_door_stop_him_and_a_plate_opens_the_door():
    w = corridor()
    w.fill(6, 1, 5, 6, 1, 5, "minecraft:oak_fence")
    assert (8, 1, 5) not in walked(w)[1]
    w = corridor()
    w.fill(6, 1, 5, 6, 1, 5, "minecraft:iron_door[facing=east,half=lower]")
    w.fill(6, 2, 5, 6, 2, 5, "minecraft:iron_door[facing=east,half=upper]")
    assert (8, 1, 5) not in walked(w)[1]
    w.fill(5, 1, 5, 5, 1, 5, "minecraft:stone_pressure_plate")
    assert (8, 1, 5) in walked(w)[1]


# Without it, the HQ sign (a wall sign at head height) would read as a wall, or a lantern there as air.
def test_a_wall_sign_at_head_height_is_no_obstacle_and_a_lantern_there_is_reported():
    w = corridor()
    w.fill(6, 2, 5, 6, 2, 5, "minecraft:warped_wall_sign[facing=east]{front_text:{messages:['{\"text\":\"A B\"}']}}")
    assert (10, 1, 5) in walked(w)[1]
    w = corridor()
    w.fill(6, 2, 5, 6, 2, 5, "minecraft:lantern[hanging=true]")
    wk, cells = walked(w)
    assert (10, 1, 5) not in cells
    seen = wk.walk([(2, 1, 5)])
    assert W.lights_at_head_height(w, wk, seen) == [(6, 2, 5, "minecraft:lantern")]


# Without it, a sign moved onto the doorstep or the guard's cell, or hung on air, would pass.
def test_the_door_sign_is_off_the_door_the_doorstep_and_the_guard_and_hangs_on_a_block():
    w = corridor(length=15)
    door, step, seat = (5, 1, 5), (6, 1, 5), (7, 1, 5)
    w.fill(4, 1, 5, 4, 3, 5, "minecraft:stone")
    w.fill(5, 3, 5, 5, 3, 5, "minecraft:stone")
    w.fill(6, 2, 5, 6, 2, 5, "minecraft:oak_wall_sign[facing=east]")       # on the doorstep's head: refused
    _s, msgs = W.sign_problems(w, door, step, seat)
    assert any("in a cell the door" in m for m in msgs) and any("hangs on" in m for m in msgs)
    w.fill(6, 2, 5, 6, 2, 5, "minecraft:air")
    w.fill(6, 3, 5, 6, 3, 5, "minecraft:oak_wall_sign[facing=east]")       # over the doorstep's head, on the stone
    signs, msgs = W.sign_problems(w, door, step, seat)
    assert signs == [(6, 3, 5)] and msgs == []


# Without it, a sign's text (spaces inside its NBT) would make the replay drop the line, or misread the block.
def test_the_reader_keeps_a_setblock_whose_nbt_has_spaces():
    op = W.parse("setblock 3444 68 3281 minecraft:warped_wall_sign[facing=east]{front_text:{messages:['{\"text\":\"THE "
                 "COMPACT\"}']}}")
    assert op[0] == "setblock" and op[1][:3] == [3444, 68, 3281] and W.base(op[1][3]) == "minecraft:warped_wall_sign"
    assert W.parse("execute as @a run fill 0 0 0 1 1 1 stone")[0] == "unparsed"
    assert W.parse("data merge block 1 2 3 {yOffset:17}") is None


# Without it, the pit's refill (replace #cobblers:rift_void) would overwrite a built cell, or never fill a void.
def test_replace_with_a_tag_writes_only_the_cells_that_match_as_they_stand():
    w = W.World((0, 0, 0, 2, 2, 2))
    w.fill(0, 0, 0, 2, 0, 2, "minecraft:stone")
    w.fill(1, 0, 1, 1, 0, 1, "minecraft:water")
    w.fill(0, 0, 0, 2, 1, 2, "minecraft:deepslate", "replace", "#cobblers:rift_void",
           {"cobblers:rift_void": ["minecraft:air", "minecraft:water"]})
    assert w.get(0, 0, 0) == "minecraft:stone" and w.get(1, 0, 1) == "minecraft:deepslate"
    assert w.get(0, 1, 0) == "minecraft:deepslate" and w.get(0, 2, 0) == "minecraft:air"
    w.fill(0, 2, 0, 0, 2, 0, "minecraft:dirt", "replace", "#minecraft:unknown_tag", {})
    assert w.get(0, 2, 0) == "minecraft:air" and w.stats["conditional_skipped"] == 1


# Without it, the Centre and Mart (placed by /place template ... 180) would land mirrored or not at all.
def test_a_template_placed_at_180_lands_where_vanilla_puts_it():
    w = W.World((0, 0, 0, 20, 10, 20))
    tpl = {"palette": [("minecraft:stone", {}), ("minecraft:structure_void", {})],
           "blocks": [(1, 0, 2, 0), (0, 0, 0, 1)], "size": [2, 1, 3]}
    w.place_template(tpl, 10, 5, 10, "180")
    assert w.get(9, 5, 8) == "minecraft:stone" and w.get(10, 5, 10) == "minecraft:air"
    w.place_template(tpl, 10, 5, 10, "clockwise_90")
    assert w.get(8, 5, 11) == "minecraft:stone"


# Without it, the replay could run the packs in an order tools/reapply.py does not, and walk a world nobody builds.
def test_the_replay_order_is_reapplys_order():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    pos = [src.find('("%s", ' % s) for s, _p, _f in W.REPLAY]
    assert all(p > 0 for p in pos), dict(zip([s for s, _p, _f in W.REPLAY], pos))
    assert pos == sorted(pos)
    # R9RU and R9HQ take their functions from their own tool's FOLDER, not from a name in reapply.py
    own = {"R9RU": "relic_underground.py", "R9HQ": "hq_tower.py"}
    for s, p, f in W.REPLAY:
        tool = (ROOT / "tools" / own[s]).read_text(encoding="utf-8") if s in own else ""
        assert ("cobblers:%s/" % f) in src or 'FOLDER = "%s"' % f in tool, (s, p)


# Without it, the audit could import the generator it checks and share its derivation (CLAUDE.md, independence).
def test_the_audit_imports_nothing_from_the_city_generator():
    src = (ROOT / "tools" / "deep_walk_audit.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+deep_city\b", src, re.M)
    assert "import deep_city" not in src and "climb_cells" not in src.split('"""', 2)[2]


# Without it, prepare would never run the walk, and a city that cannot be climbed would ship again.
def test_prepare_runs_the_walk_after_the_city_and_relic_builds():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    walk = src.find('"deep_walk_audit.py"')
    assert walk > src.find('"deep_city.py", "build"') > 0
    assert walk > src.find('"relic_underground.py", *src, "build"') > 0
    assert walk > src.find('"habitat_blocks.py", "function"') > 0


# ------------------------------------------------------------------ the real build

def _source_root():
    r = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not r or not Path(r).is_dir():
        pytest.skip("no COBBLERS_SOURCE_ROOT: the walk's ground is the heightmap")
    missing = [p for p in NEEDED if not (W.PACKS / p).is_dir()]
    if missing or not W.PLAN.is_file():
        pytest.skip("not built here: %s" % (missing or [str(W.PLAN)]))
    return r


@pytest.mark.slow
# Without it, the built Deep could stop being walkable (a ring, the lip, a tier or the crown cut off) unnoticed.
def test_the_built_deep_is_walked_clean_with_one_roofed_tower_under_its_lift(tmp_path):
    root = _source_root()
    rep = tmp_path / "report.json"
    rc = W.main(["--source-root", root, "--report", str(rep)])
    r = json.loads(rep.read_text(encoding="utf-8"))
    assert rc == 0, r["problems"]
    st = r["stats"]
    stopped = {k for k, v in st["towers"].items() if v != "climbs"}
    assert stopped == {str(LIFT_TOWER)}
    assert st["towers"][str(TWIN)] == "climbs"
    assert [r_[2] for r_ in st["roofed_steps"]] == [[3540, 32, 3243]]
    assert all(st["tiers"].values()) and len(st["tiers"]) == 7 and st["crown"] > 0
    assert st["way_lights"] == 15 and len({tuple(c) for c in st["way_light_cells"]}) == 15


@pytest.mark.slow
# Without it, nothing shows the walk bites on the GENERATOR: a record-side mutation proves nothing (CLAUDE.md).
def test_a_roof_put_back_in_the_generator_over_one_step_fails_the_walk_and_names_it(tmp_path):
    root = _source_root()
    import deep_city as DC
    orig = DC.build_tower
    put = []

    def roofed(cv, P, M, t, name, palette, sign=None, pylon=4, walls_to=None, exits=(), roof=True, owner="tower"):
        cols = orig(cv, P, M, t, name, palette, sign, pylon, walls_to, exits, roof, owner)
        w = DC.frame(t["anchor"], t["back"])
        if roof and tuple(w(*t["door"])) == TWIN:
            x, z = w(*DC.ring_cells()[(t["R"] - 4) % 16])
            y = walls_to if walls_to is not None else t["gu"]
            cv.put(x, y, z, P("tread"), owner=owner)
            put.append((x, y, z))
        return cols
    mp = pytest.MonkeyPatch()
    mp.setattr(DC, "build_tower", roofed)
    mp.setattr(DC, "OUT", tmp_path / "cobblers_deep_city")
    mp.setattr(DC, "PLAN", tmp_path / "plan.json")
    try:
        cv, plan, services, _spec = DC.build(root)
        DC.emit(cv, services, plan)
    finally:
        mp.undo()
    assert len(put) == 1
    rep = tmp_path / "report.json"
    rc = W.main(["--source-root", root, "--plan", str(tmp_path / "plan.json"), "--city-pack",
                 str(tmp_path / "cobblers_deep_city"), "--report", str(rep)])
    probs = json.loads(rep.read_text(encoding="utf-8"))["problems"]
    assert rc == 1
    named = [m for k, m in probs if k == "towers" and str(TWIN) in m]
    assert named, probs
    assert "step 14 " in named[0] and str(put[0]) in named[0], named[0]
