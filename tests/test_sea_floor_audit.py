"""tools/sea_floor_audit.py against a synthetic 64 x 64 sea whose every expected value is computable by hand.

The fixture: sea level y62; land (ground y70) in the strip x 0-7, so a sea column's distance from land is x - 7 along
its row; every other column is seabed at y50. Two marine regions split the map at z32: `north` (frozen_ocean north of
z16 at 20 or more from land, deep_frozen_ocean north of z16 at or below y36) and `south` (warm_ocean within 10 of land
above y36); both have a 40-block shelf. The clean pack: one kelp at (20, 40) (13 from land, so lukewarm), stems
y51-56 and an age-25 head at y57; a seagrass at (12, 10); a tall seagrass at (14, 20); a run of three seagrass at
x15-17, z40. Each test breaks one property and expects that check, and only that check, to report.

What this does NOT cover: the real pack against the real heightmap (the prepare job `sea_floor_audit` runs that), and
anything in a running game.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sea_floor_audit as A  # noqa: E402

N = 64
SEA = 62
OCEAN_TEXT = """
| Flora | Vanilla biomes | Planned in | Depth |
| --- | --- | --- | --- |
| Kelp | ocean, lukewarm, cold, and their deep variants; not warm or frozen | shelves | y28–58 |
| Seagrass | every ocean except frozen | every shelf outside frozen water | y40–60 |
"""
REGIONS = {"marine_regions": [
    {"id": "north", "polygons": [[[0, 0], [N, 0], [N, 32], [0, 32]]],
     "seabed_plan": {"shelf_width_blocks": 40},
     "biomes": {"rules": ["deep_frozen_ocean: north of z16 where the planned seabed is at or below y36",
                          "frozen_ocean: north of z16, 20 or more blocks from land, seabed above y36",
                          "cold_ocean: everything else in the zone"]}},
    {"id": "south", "polygons": [[[0, 32], [N, 32], [N, N], [0, N]]],
     "seabed_plan": {"shelf_width_blocks": 40},
     "biomes": {"rules": ["deep_lukewarm_ocean: planned seabed at or below y36",
                          "warm_ocean: shelf within 10 blocks of land", "lukewarm_ocean: the rest of the shelf"]}},
    {"id": "no_polygons", "biomes": {"rules": []}},
]}
LOAD = "forceload add 0 0 63 63"
FREE = "forceload remove 0 0 63 63"
CLEAN = [
    "fill 20 51 40 20 56 40 minecraft:kelp_plant replace minecraft:water",
    "fill 20 57 40 20 57 40 minecraft:kelp[age=25] replace minecraft:water",
    "fill 12 51 10 12 51 10 minecraft:seagrass replace minecraft:water",
    "fill 14 51 20 14 51 20 minecraft:tall_seagrass[half=lower] replace minecraft:water",
    "fill 14 52 20 14 52 20 minecraft:tall_seagrass[half=upper] replace minecraft:water",
    "fill 15 51 40 17 51 40 minecraft:seagrass replace minecraft:water",
]


def ground():
    g = np.full((N, N), 50, np.int16)
    g[:, :8] = 70
    return g


def env(g=None, **kw):
    kw.setdefault("sea_life_cols", np.zeros((N, N), bool))     # the sea_life pack built, writing nothing here
    bands = A.ocean_bands(OCEAN_TEXT)
    return A.Env(g if g is not None else ground(), SEA, bands, A.region_rules(REGIONS), ["north", "south"], **kw)


def pack(tmp_path, body, extra=None, index=None, load=True):
    fn = tmp_path.joinpath(*A.FN)
    fn.mkdir(parents=True)
    lines = ([LOAD] if load else []) + list(body) + ([FREE] if load else [])
    (fn / "1flora_0_0.mcfunction").write_text("\n".join(["# test"] + lines) + "\n", encoding="utf-8")
    names = ["1flora_0_0"]
    for name, ls in (extra or {}).items():
        (fn / (name + ".mcfunction")).write_text("\n".join(ls) + "\n", encoding="utf-8")
        names.append(name)
    (fn / "index.txt").write_text("\n".join(index if index is not None else names) + "\n", encoding="utf-8")
    return tmp_path


def run(tmp_path, body, e=None, **kw):
    return A.audit(e or env(), pack(tmp_path, body, **kw))


def failing(res):
    return {k for k, v in res["problems"].items() if v}


# ------------------------------------------------------------------------------------------- the clean pack


def test_clean_pack_passes_with_hand_counted_coverage(tmp_path):
    # Without it, every other test's "only this check fails" has no baseline and could pass on a broken audit.
    res = run(tmp_path, CLEAN)
    assert failing(res) == set(), res["problems"]
    assert res["commands"] == 6
    assert res["cells"] == 6 + 1 + 1 + 2 + 3
    assert res["kelp_columns"] == 1
    assert res["seagrass_columns"] == 5          # (12, 10), (14, 20) tall, (15..17, 40)
    assert res["tall_seagrass"] == 1
    assert res["kelp_top_highest"] == 57
    assert res["forceloaded_chunks"] == 16       # chunks 0-3 x 0-3
    assert res["regions"]["north"]["seagrass_columns"] == 2
    assert res["regions"]["south"]["kelp_columns"] == 1


# ------------------------------------------------------------------------------------------- the writes


def test_every_fill_must_replace_only_water(tmp_path):
    # Without it, a fill could overwrite a block another pack or the export put in the sea.
    body = CLEAN[:-1] + ["fill 15 51 40 17 51 40 minecraft:seagrass"]
    assert failing(run(tmp_path, body)) == {"water"}


def test_a_cell_in_land_is_not_water(tmp_path):
    # Without it, a plant written into a land column (ground y70) would pass as sea flora.
    assert failing(run(tmp_path, CLEAN + ["fill 3 71 30 3 71 30 minecraft:seagrass replace minecraft:water"])) \
        >= {"water"}


def test_a_lake_column_is_not_sea(tmp_path):
    # Without it, the sea pack could dress a lake the lake pack owns.
    e = env(lakes=[(60, [[(10, 0), (13, 0), (13, 13), (10, 13)]], (10, 0, 13, 13))])
    assert failing(run(tmp_path, CLEAN, e)) == {"water"}


def test_only_the_four_plants_and_a_stopped_kelp_head(tmp_path):
    # Without it, a kelp head of age 0 (which grows to the surface) or any other block would pass.
    body = list(CLEAN)
    body[1] = "fill 20 57 40 20 57 40 minecraft:kelp[age=3] replace minecraft:water"
    assert "blocks" in failing(run(tmp_path, body))


def test_no_cell_is_written_twice(tmp_path):
    # Without it, a second write whose `replace minecraft:water` finds a plant (and does nothing) goes unseen.
    assert "cells" in failing(run(tmp_path, CLEAN + [CLEAN[2]]))


# ------------------------------------------------------------------------------------------- the seabed and bands


def test_a_plant_must_stand_on_its_ground(tmp_path):
    # Without it, a seagrass floating a block above the seabed (it pops off in game) would pass.
    body = CLEAN[:2] + ["fill 12 52 10 12 52 10 minecraft:seagrass replace minecraft:water"] + CLEAN[3:]
    assert failing(run(tmp_path, body)) == {"seabed"}


def test_kelp_without_its_head_is_not_a_plant(tmp_path):
    # Without it, a stem with no age-25 head (it grows on) or a broken column would pass.
    assert failing(run(tmp_path, [CLEAN[0]] + CLEAN[2:])) == {"seabed"}


def test_kelp_tops_stay_three_under_the_surface(tmp_path):
    # Without it, a kelp head at sea - 2 (a rest point on a crossing) would pass.
    body = ["fill 20 51 40 20 59 40 minecraft:kelp_plant replace minecraft:water",
            "fill 20 60 40 20 60 40 minecraft:kelp[age=25] replace minecraft:water"] + CLEAN[2:]
    assert failing(run(tmp_path, body)) == {"bands"}


def test_seagrass_ground_must_be_in_oceans_band(tmp_path):
    # Without it, seagrass below OCEAN.md's y40 floor would pass.
    g = ground()
    g[50, 30] = 39
    body = CLEAN + ["fill 30 40 50 30 40 50 minecraft:seagrass replace minecraft:water"]
    assert failing(run(tmp_path, body, env(g))) == {"bands"}


def test_kelp_ground_must_be_in_oceans_band(tmp_path):
    # Without it, kelp on a y59 shoal (outside y28-58) would pass.
    g = ground()
    g[45, 30] = 27
    body = CLEAN + ["fill 30 28 45 30 40 45 minecraft:kelp_plant replace minecraft:water",
                    "fill 30 41 45 30 41 45 minecraft:kelp[age=25] replace minecraft:water"]
    assert failing(run(tmp_path, body, env(g))) == {"bands"}


# ------------------------------------------------------------------------------------------- the regions


def test_no_kelp_in_warm_water(tmp_path):
    # Without it, kelp within the south's 10 blocks of land (warm_ocean) would pass.
    body = CLEAN + ["fill 12 51 44 12 56 44 minecraft:kelp_plant replace minecraft:water",
                    "fill 12 57 44 12 57 44 minecraft:kelp[age=25] replace minecraft:water"]
    res = run(tmp_path, body)
    assert failing(res) == {"regions"}
    assert res["regions"]["south"]["kelp_in_warm_ocean"] == 1


def test_seagrass_is_allowed_in_warm_water(tmp_path):
    # Without it, the warm rule could be over-applied to seagrass (OCEAN.md grows seagrass in every unfrozen ocean).
    assert failing(run(tmp_path, CLEAN + ["fill 9 51 50 9 51 50 minecraft:seagrass replace minecraft:water"])) == set()


def test_nothing_in_frozen_water(tmp_path):
    # Without it, seagrass 33 from land north of z16 (frozen_ocean) would pass.
    res = run(tmp_path, CLEAN + ["fill 40 51 5 40 51 5 minecraft:seagrass replace minecraft:water"])
    assert failing(res) == {"regions"}
    assert res["regions"]["north"]["in_frozen_ocean"] == 1


def test_frozen_starts_at_exactly_its_distance(tmp_path):
    # Without it, an off-by-one in "20 or more from land" would go unseen: x27 is 20 from land x7, x26 is 19.
    assert failing(run(tmp_path, CLEAN + ["fill 26 51 5 26 51 5 minecraft:seagrass replace minecraft:water"])) == set()
    res = run(tmp_path / "b", CLEAN + ["fill 27 51 5 27 51 5 minecraft:seagrass replace minecraft:water"])
    assert res["regions"]["north"]["in_frozen_ocean"] == 1


def test_no_kelp_in_deep_frozen_water(tmp_path):
    # Without it, kelp on y30 seabed north of z16, near land (deep_frozen_ocean by the rule order), would pass.
    g = ground()
    g[8, 10] = 30
    body = CLEAN + ["fill 10 31 8 10 40 8 minecraft:kelp_plant replace minecraft:water",
                    "fill 10 41 8 10 41 8 minecraft:kelp[age=25] replace minecraft:water"]
    res = run(tmp_path, body, env(g))
    assert failing(res) == {"regions"}
    assert res["regions"]["north"]["in_deep_frozen_ocean"] == 1


def test_nothing_beyond_the_shelf(tmp_path):
    # Without it, flora 53 blocks out against a 40-block shelf would pass.
    res = run(tmp_path, CLEAN + ["fill 60 51 40 60 51 40 minecraft:seagrass replace minecraft:water"])
    assert failing(res) == {"regions"}
    assert res["regions"]["south"]["beyond_shelf"] == 1


def test_a_column_outside_every_polygon_takes_the_nearest(tmp_path):
    # Without it, a column in no polygon would escape every regional rule.
    regions = json.loads(json.dumps(REGIONS))
    regions["marine_regions"][0]["polygons"] = [[[0, 0], [N, 0], [N, 30], [0, 30]]]
    regions["marine_regions"][1]["polygons"] = [[[0, 34], [N, 34], [N, N], [0, N]]]   # z30-33 in neither
    # (12, 33) is 3 from the north polygon's edge and 1 from the south's: the south's warm rule applies
    e = A.Env(ground(), SEA, A.ocean_bands(OCEAN_TEXT), A.region_rules(regions), ["north", "south"],
              sea_life_cols=np.zeros((N, N), bool))
    body = CLEAN + ["fill 12 51 33 12 56 33 minecraft:kelp_plant replace minecraft:water",
                    "fill 12 57 33 12 57 33 minecraft:kelp[age=25] replace minecraft:water"]
    res = run(tmp_path, body, e)
    assert res["regions"]["south"]["kelp_in_warm_ocean"] == 1
    assert res["regions"]["south"]["by_nearest_polygon"] == 1


# ------------------------------------------------------------------------------------------- clear and owned


def test_no_column_in_an_excluded_box(tmp_path):
    # Without it, flora inside a town, a portal, a dock or the Deep would pass.
    res = run(tmp_path, CLEAN, env(keep_out=[("portal p", (11, 9, 13, 11))]))
    assert failing(res) == {"clear"}


def test_no_column_in_a_ferry_lane(tmp_path):
    # Without it, kelp under a ferry line would pass.
    res = run(tmp_path, CLEAN, env(lanes=[("ferry lane l", [(20, 30), (20, 50)], 1)]))
    assert failing(res) == {"clear"}


def test_no_seagrass_in_a_gate_clearance_but_kelp_may_stand_there(tmp_path):
    # Without it, the gate rule could miss seagrass, or wrongly forbid deep kelp the data allows.
    res = run(tmp_path, CLEAN, env(gates=[("g", (20, 38), (20, 42))], gate_clearance=1))
    assert failing(res) == set()
    assert res["clear"]["kelp_columns_in_gate_clearance"] == 1
    res = run(tmp_path / "b", CLEAN, env(gates=[("g", (12, 8), (12, 12))], gate_clearance=1))
    assert failing(res) == {"clear"}


def test_three_clear_of_every_sea_life_column(tmp_path):
    # Without it, the two water packs could share or abut a column; x15 is 3 from x18, x14 is 4 from it.
    sl = np.zeros((N, N), bool)
    sl[40, 18] = True
    assert "owned" in failing(run(tmp_path, CLEAN, env(sea_life_cols=sl)))
    sl = np.zeros((N, N), bool)
    sl[40, 21 + 3] = True      # 4 from the kelp at x20... and the run ends at x17
    assert failing(run(tmp_path / "b", CLEAN, env(sea_life_cols=sl))) == set()


def test_an_absent_sea_life_pack_is_reported_not_skipped(tmp_path):
    # Without it, a missing sea_life build would make the margin check pass vacuously.
    res = A.audit(env(sea_life_cols=None), pack(tmp_path, CLEAN))
    assert res["owned"].get("within_margin_of_sea_life") is None
    assert any("absent" in p for p in res["problems"]["owned"])


def test_no_column_in_a_sea_life_coast_within_its_reach(tmp_path):
    # Without it, the open-sea pack could dress the coasts sea_life owns; (12, 10) is 5 from land.
    sl = np.zeros((N, N), bool)
    res = run(tmp_path, CLEAN, env(sea_life_cols=sl, coasts=[("c", (10, 0, 30, 15))], coast_reach=5))
    assert failing(res) == {"owned"}
    res = run(tmp_path / "b", CLEAN, env(sea_life_cols=sl, coasts=[("c", (10, 0, 30, 15))], coast_reach=4))
    assert failing(res) == set()


def test_nothing_inside_the_reef_disc(tmp_path):
    # Without it, flora could crowd the Relic reef; (20, 40) is exactly 5 from (23, 36).
    sl = np.zeros((N, N), bool)
    assert failing(run(tmp_path, CLEAN, env(sea_life_cols=sl, reef=(23.0, 36.0, 5.0)))) == {"owned"}
    assert failing(run(tmp_path / "b", CLEAN, env(sea_life_cols=sl, reef=(23.0, 36.0, 4.9)))) == set()


def test_no_cell_another_water_pack_writes(tmp_path):
    # Without it, a cell the drift pack built could be counted ours (or ours could block theirs).
    sl = np.zeros((N, N), bool)
    res = run(tmp_path, CLEAN, env(sea_life_cols=sl, foreign={"cobblers_sea_drift": {(20, 40): [(55, 55, "glass")]},
                                                              "cobblers_portals": None}))
    assert failing(res) == {"owned"}
    assert res["owned"]["foreign"]["cobblers_portals"] == "absent: not checked"


# ------------------------------------------------------------------------------------------- policy, functions


def test_spawn_condition_blocks_need_a_policy_entry_for_this_pack(tmp_path):
    # Without it, seagrass (Pincurchin's nearby block) could spread a spawn condition across the sea unreviewed.
    sl = np.zeros((N, N), bool)
    res = run(tmp_path, CLEAN, env(sea_life_cols=sl, spawn_blocks={"minecraft:seagrass"}))
    assert failing(res) == {"policy"}
    pol = {"whitelist": [{"blocks": ["minecraft:seagrass"], "scope": "the open sea floor (cobblers_sea_floor)"}]}
    res = run(tmp_path / "b", CLEAN, env(sea_life_cols=sl, spawn_blocks={"minecraft:seagrass"}, policy=pol))
    assert failing(res) == set()


def test_forceload_adds_and_removes_balance(tmp_path):
    # Without it, a function that leaves chunks force-loaded forever would pass.
    body = [LOAD] + CLEAN
    assert "forceload" in failing(run(tmp_path, body, load=False))


def test_a_fill_before_its_forceload_is_reported(tmp_path):
    # Without it, a write into an unloaded chunk (which the server silently skips) would pass.
    body = CLEAN + [LOAD, FREE]
    assert "forceload" in failing(run(tmp_path, body, load=False))


def test_a_function_missing_from_the_index_never_runs(tmp_path):
    # Without it, a function on disk that reapply.py never calls would be counted as built.
    res = run(tmp_path, CLEAN, extra={"1flora_0_1": [LOAD, FREE]}, index=["1flora_0_0"])
    assert failing(res) == {"parse"}


def test_an_absent_or_empty_pack_fails_closed(tmp_path):
    # Without it, a build that wrote nothing (or was never run) would audit clean.
    assert "parse" in failing(A.audit(env(), tmp_path / "nowhere"))
    res = run(tmp_path, [])
    assert res["kelp_columns"] == 0 and "regions" in failing(res)


def test_an_unknown_command_is_reported(tmp_path):
    # Without it, a setblock or a kill hidden in the pack would go unchecked.
    assert "parse" in failing(run(tmp_path, CLEAN + ["setblock 20 58 40 minecraft:stone"]))


# ------------------------------------------------------------------------------------------- the helpers


def test_land_distance_is_exact_euclidean():
    # Without it, a coarse or chamfer distance (the builder's) could hide in the audit; (3, 4) is exactly 5 from (0, 0).
    land = np.zeros((20, 20), bool)
    land[0, 0] = True
    L = A.LandIndex(land)
    assert L.within(np.array([3]), np.array([4]), 25).tolist() == [True]
    assert L.within(np.array([3]), np.array([4]), 24).tolist() == [False]


def test_land_distance_matches_brute_force():
    # Without it, the summed-area shortcut (box, then disc rows) could disagree with the definition somewhere.
    rnd = random.Random(1004)
    land = np.zeros((48, 48), bool)
    for _ in range(25):
        land[rnd.randrange(48), rnd.randrange(48)] = True
    L = A.LandIndex(land)
    lz, lx = np.nonzero(land)
    xs = np.array([rnd.randrange(48) for _ in range(300)])
    zs = np.array([rnd.randrange(48) for _ in range(300)])
    for r2 in (0, 2, 50, 99, 100, 101, 400):
        want = [bool(((lx - x) ** 2 + (lz - z) ** 2 <= r2).any()) for x, z in zip(xs, zs)]
        assert L.within(xs, zs, r2).tolist() == want


def test_polygon_and_nearest_helpers():
    # Without it, a region label could be wrong for every column: a unit square tested inside, outside and by distance.
    ring = [[[0, 0], [10, 0], [10, 10], [0, 10]]]
    assert A.points_in_rings(ring, np.array([5.0, 15.0]), np.array([5.0, 5.0])).tolist() == [True, False]
    assert A.dist_to_rings(ring, np.array([13.0]), np.array([14.0])).tolist() == [5.0]


# ------------------------------------------------------------------------------------------- the real design files


def test_the_rules_the_audit_enforces_are_still_stated_in_the_design():
    # Without it, a reworded OCEAN.md table or regions.json rule would silently drop a check.
    bands = A.ocean_bands((ROOT / "docs" / "world-building" / "OCEAN.md").read_text(encoding="utf-8"))
    assert bands["kelp"][0] < bands["kelp"][1] and bands["seagrass"][0] < bands["seagrass"][1]
    rules = A.region_rules(json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8")))
    assert "frozen_from_land" in rules["frostwater_shelf"] and "deep_frozen_at_or_below_y" in rules["frostwater_shelf"]
    assert "warm_within" in rules["southern_shallows"]
    for rid in ("frostwater_shelf", "windward_deep", "eastern_reach", "southern_shallows"):
        assert rules[rid]["reach"] > 0


def test_the_audit_runs_after_the_pack_it_reads_in_prepare():
    # Without it, prepare could audit a stale pack, or never audit this one at all.
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    b = text.index('add("sea_floor:build"')
    a = text.index('add("sea_floor_audit", "sea_floor_audit.py"')
    assert a > b


def test_the_audit_does_not_import_its_builder():
    # Without it, the audit could derive its expectations from tools/sea_floor.py and agree with any bug in it.
    src = (ROOT / "tools" / "sea_floor_audit.py").read_text(encoding="utf-8")
    for bad in ("import sea_floor", "from sea_floor", "import sea_life as", "import sea_life\n", "plan.json\")"):
        assert bad not in src
