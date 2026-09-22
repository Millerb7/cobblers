"""tools/rift_fracture.py: the Rift as a fracture, the prototype stretch.

Written in the same session as the builder. Tests that need the plan build it from the canonical heightmap and skip
when it is not on this machine (COBBLERS_SOURCE_ROOT or C:/Users/wnd/Documents); the fail-closed tests do not.
"""
import json
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits as FL  # noqa: E402
import rift_fracture as RF  # noqa: E402

SOURCE = os.environ.get("COBBLERS_SOURCE_ROOT") or r"C:\Users\wnd\Documents"


@pytest.fixture(scope="module")
def plan():
    try:
        return RF.build(SOURCE)
    except Exception as e:  # no heightmap on this machine
        pytest.skip("the canonical heightmap is not available: %s" % e)


def test_the_cut_only_ever_removes(plan):
    # Cut only: the rim and the floor edge stay, so nothing on the plateau or the floor (Victory Road, the League)
    # is buried or lifted.
    assert plan.top and all(y <= plan.old[k] for k, y in plan.top.items())


def test_the_lip_is_a_lethal_drop_where_the_depth_allows(plan):
    # The scarps are the barrier: a riser of 23 or more cannot be survived, so the lip is not a way down.
    fr = plan.frame
    deep = 0
    for st in plan.stations[5:-5]:
        for side in (-1, 1):
            sd = st["sides"][side]
            D = sd["rim_y"] - st["floor"]
            if D < 52 or any(es_side == side and abs(st["s"] - es) <= gap + 14
                             for es_side, es, gap in plan.entrance_spans):
                continue            # an entrance is a way down on purpose
            x, z = map(round, fr.xz(st["s"], sd["rim_t"] - side * 2))
            y = plan.top.get((x, z))
            assert y is not None and sd["rim_y"] - y >= 23, (st["s"], side, sd["rim_y"], y)
            deep += 1
    assert deep > 20


def test_every_riser_below_the_lip_is_too_high_to_walk(plan):
    # Down the whole wall, not just at the lip: every step between neighbouring columns in the cut band is either
    # walkable (0-1) or a riser of 2 or more; the old 17-degree slope must not survive as a ramp from lip to floor.
    fr = plan.frame
    ramps = 0
    for st in plan.stations[5:-5:5]:
        for side in (-1, 1):
            sd = st["sides"][side]
            cols = [plan.top.get(tuple(map(round, fr.xz(st["s"], t)))) for t in
                    range(sd["rim_t"] - side * 2, sd["edge_t"], -side)]
            cols = [c for c in cols if c is not None]
            # a walkable ramp is a run of 1-block drops from the lip's foot all the way down
            run = max((len(list(g)) for k, g in __import__("itertools").groupby(
                (0 <= a - b <= 1) for a, b in zip(cols, cols[1:])) if k), default=0)
            ramps += run > 60
    assert ramps == 0


def test_the_biome_never_leaves_the_lip(plan):
    # The crossing is the moment: a cell with any column outside the lip would tint the sky before you arrive.
    cells = RF.biome_cells(plan)
    assert cells
    for cx, cz in cells:
        for i in range(4):
            for j in range(4):
                v = plan.inside.get((cx * 4 + i, cz * 4 + j))
                assert v is not None and v[3] >= 0


def test_nothing_placed_conditions_a_spawn(plan):
    # Spawns are assigned by biome and region; a placed block that a spawn condition names would decide encounters.
    policy = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    used = {b.split("[")[0] for b in plan.put.values()}
    spec = json.loads((ROOT / "data" / "rift_fracture.json").read_text(encoding="utf-8"))
    allowed = {"minecraft:water"} if spec["waterfalls"].get("spawn_policy_exception") else set()
    assert used and not (used & set(policy) - allowed), used & set(policy)
    # the one exception is the deliberate waterfall, and only as many sources as it has
    assert sum(1 for b in plan.put.values() if b == "minecraft:water") == len(plan.water) <= 2 * spec["waterfalls"]["count"]


def test_nothing_that_walks_can_be_trapped(plan):
    # The owner's worry (2026-09-22): Pokemon running about get stuck in the crevices. Every column must reach the
    # stretch's edge by steps of at most one block up; falling is allowed. Fails closed: the build refuses otherwise.
    traps, ours = RF.trap_cells(plan)
    assert ours == []
    assert plan.caps, "no crack was capped: the check would be passing on nothing"


def test_every_deep_crack_is_capped_with_glass_at_ground_level(plan):
    # Nothing can fall into a crack deeper than one block; purple glass where it glows, tinted where it is dark.
    spec = json.loads((ROOT / "data" / "rift_fracture.json").read_text(encoding="utf-8"))["caps"]
    for (x, z), y in plan.caps.items():
        assert plan.put.get((x, y, z)) in (spec["glow"], spec["dark"]), (x, y, z)
        assert plan.top.get((x, z), y) <= y - 2 or plan.top.get((x, z), y) == y


def test_the_entrance_is_a_gap_in_the_crags_with_the_guard_in_the_open(plan):
    # A gap, not a gatehouse: no upthrust rock on the path, and the trailhead guard stands in the open.
    assert plan.path and not (set(plan.path) & set(plan.crag))
    guards = [c for c in plan.entities if "armor_stand" in c]
    assert len(guards) == 1 and "guard" in guards[0].lower()


def test_the_rim_is_high_where_it_is_crags_and_higher_at_the_peaks(plan):
    # What the owner liked in the first pass: height seen from far away. Crags 20-80 over the plateau, peaks higher.
    over = sorted(plan.crag[k] - plan.old[k] for k in plan.crag)
    assert over and sum(1 for h in over if h >= 20) > 1000
    assert over[-1] >= 100


def test_the_build_is_the_same_every_time():
    # Re-appliable after a re-export: the same data and heightmap must lay the same Rift.
    try:
        a, b = RF.build(SOURCE), RF.build(SOURCE)
    except Exception as e:
        pytest.skip("the canonical heightmap is not available: %s" % e)
    assert a.top == b.top and a.put == b.put and a.entities == b.entities


def test_portal_sheets_force_load_wait_kill_then_summon(plan):
    # Entities load about 20 ticks after their chunk: killing before they load and summoning again stacked 26 traders
    # on 6 stalls. The sheets' function force-loads, schedules the rest after the wait, kills its own tag, summons.
    fns, sel, n = RF.fx_functions(plan)
    first, go = [fns[k] for k in sorted(fns)]
    assert any(l.startswith("forceload add") for l in first)
    wait = [l for l in first if l.startswith("schedule function")]
    assert wait and int(wait[0].split()[-2].rstrip("t")) >= 40
    kills = [i for i, l in enumerate(go) if l.startswith("kill ")]
    summons = [i for i, l in enumerate(go) if l.startswith("summon ")]
    assert kills and summons and max(kills) < min(summons) and len(summons) == n == 4
    # the kill takes every entity of the stretch, whatever its type, so a re-run never stacks a guard
    assert all(l.split("[")[1].startswith("tag=") for l in go if l.startswith("kill "))
    for l in first + go:
        assert "tag=rift_fx_" in l or not l.startswith(("kill", "execute store"))
    assert FL.check_lines(first, "fx") == [] or all("chunks" not in p[2] for p in FL.check_lines(first, "fx"))


def test_every_sheet_glows_and_culls_by_its_own_size(plan):
    # Brightness 15 so it glows in the dark; a culling box as large as the sheet, so a big sheet does not vanish
    # when its origin leaves the screen.
    sheets = [c for c in plan.entities if "block_display" in c]
    assert len(sheets) == 3
    for c in sheets:
        assert "brightness:{sky:15,block:15}" in c and "nether_portal" in c
        w = float(c.split("width:")[1].split("f")[0])
        scale = [float(v.rstrip("f")) for v in c.split("scale:[")[1].split("]")[0].split(",")]
        assert w >= max(scale)


def test_verify_fails_without_a_plan(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(RF, "PLAN", tmp_path / "none.json")
    assert RF.verify(tmp_path) == 1
    assert "FAIL" in capsys.readouterr().out


def test_verify_fails_when_the_plan_expects_no_entities(tmp_path, monkeypatch, capsys):
    # Fail closed: a plan that counts no sheets cannot call the sheets present.
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"checks": [[0, 0, 0, ["minecraft:air"], k] for k in
                                        ("cut: air above the new ground", "vein", "sky crack", "light block",
                                         "crag top", "crack cap", "entrance path")],
                             "entities_expected": 0}), encoding="utf-8")
    monkeypatch.setattr(RF, "PLAN", p)
    assert RF.verify(tmp_path) == 1
