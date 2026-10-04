"""The builder's own tests for tools/sea_floor.py (the open sea's kelp forests and seagrass meadows).

These check the generator's pieces on synthetic input and the data file's internal consistency; the built pack is
checked only if it is present. The INDEPENDENT audit of the pack is another hand's and is not here.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits as FL  # noqa: E402
import sea_floor as SF        # noqa: E402

SEA = 62
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+) replace minecraft:water$")


def spec():
    return SF.load()


def fake_model(kelp=(), grass=(), N=256):
    m = SimpleNamespace()
    m.spec = spec()
    m.sea = SEA
    m.N = N
    m.kelp = list(kelp)
    m.grass = list(grass)
    m.lines = {}
    m.problems = []
    m.X = np.zeros((N, N), bool)
    m.sl_cols = np.zeros((N, N), bool)
    m.sl = SimpleNamespace(ex=SimpleNamespace(gate=np.zeros((N, N), bool)))
    m.names = ["r"]
    m.stats = {"r": {"kelp_columns": len(m.kelp), "seagrass_columns": len(m.grass)}}
    return m


# ------------------------------------------------------------------ the data

def test_data_regions_are_marine_regions_in_sea_life_order():
    s = spec()
    import sea_life
    order = sea_life.load()["finds"]["region_order"]
    ids = [k for k in s["regions"] if k not in ("from", "unassigned_why")]
    assert ids and set(ids) <= set(order)
    doc = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    marine = {r["id"]: r for r in doc["marine_regions"]}
    for rid in ids:
        assert marine[rid].get("polygons"), rid
        assert marine[rid]["seabed_plan"]["shelf_width_blocks"] > 0, rid


def test_data_kelp_never_reaches_within_two_of_the_surface():
    s = spec()
    gap = int(s["kelp"]["max_top_below_surface"])
    assert gap >= 3
    assert s["kelp"]["ground_y"][1] < SEA - gap          # room for at least a head
    assert int(s["kelp"]["age"]) == 25                    # never grows past its top


def test_data_seagrass_stays_under_water_and_writes_only_water():
    s = spec()
    assert s["seagrass"]["ground_y"][1] <= SEA - 2
    assert s["writes"]["filter"] == "minecraft:water"


def test_data_no_coral_is_built():
    s = spec()
    assert s["regions"]["southern_shallows"].get("coral") is False
    src = (ROOT / "tools" / "sea_floor.py").read_text(encoding="utf-8")
    assert "_coral" not in src.replace('"coral" in b', "")


def test_function_tile_is_a_multiple_of_the_run_tile():
    assert SF.FN_TILE % SF.TILE == 0


# ------------------------------------------------------------------ lines()

def test_kelp_is_a_stem_and_a_head_with_the_water_filter():
    m = fake_model(kelp=[(10, 20, 40, 50), (11, 20, 40, 41)])
    out = SF.lines(m)["flora"]
    assert out == [
        "fill 10 41 20 10 49 20 minecraft:kelp_plant replace minecraft:water",
        "fill 10 50 20 10 50 20 minecraft:kelp[age=25] replace minecraft:water",
        "fill 11 41 20 11 41 20 minecraft:kelp[age=25] replace minecraft:water",
    ]


def test_seagrass_runs_merge_and_break_on_height_tall_and_tile():
    grass = [(1, 5, 50, False), (2, 5, 50, False), (3, 5, 50, False),   # one run
             (4, 5, 51, False),                                          # height change: a new run
             (5, 5, 51, True),                                           # tall: its own two halves
             (6, 5, 51, False),
             (63, 7, 50, False), (64, 7, 50, False)]                     # across a 64 tile: two runs
    out = SF.lines(fake_model(grass=grass))["flora"]
    assert "fill 1 51 5 3 51 5 minecraft:seagrass replace minecraft:water" in out
    assert "fill 4 52 5 4 52 5 minecraft:seagrass replace minecraft:water" in out
    assert "fill 5 52 5 5 52 5 minecraft:tall_seagrass[half=lower] replace minecraft:water" in out
    assert "fill 5 53 5 5 53 5 minecraft:tall_seagrass[half=upper] replace minecraft:water" in out
    assert out.index("fill 5 52 5 5 52 5 minecraft:tall_seagrass[half=lower] replace minecraft:water") < \
        out.index("fill 5 53 5 5 53 5 minecraft:tall_seagrass[half=upper] replace minecraft:water")
    assert "fill 6 52 5 6 52 5 minecraft:seagrass replace minecraft:water" in out
    assert "fill 63 51 7 63 51 7 minecraft:seagrass replace minecraft:water" in out
    assert "fill 64 51 7 64 51 7 minecraft:seagrass replace minecraft:water" in out
    cols = 0
    for ln in out:
        g = FILL.match(ln)
        assert g, ln
        if g.group(7) == "minecraft:seagrass":
            cols += int(g.group(4)) - int(g.group(1)) + 1
    assert cols == sum(1 for c in grass if not c[3])


# ------------------------------------------------------------------ checks()

def test_checks_refuse_a_kelp_top_near_the_surface_and_seagrass_in_a_gate():
    m = fake_model(kelp=[(3, 3, 40, SEA - 2)], grass=[(4, 4, 50, False)])
    m.sl.ex.gate[4, 4] = True
    SF.lines(m)
    SF.checks(m)
    assert any("above sea" in p for p in m.problems)
    assert any("gate" in p for p in m.problems)


def test_checks_refuse_an_excluded_column_and_an_empty_region():
    m = fake_model(kelp=[(3, 3, 40, 50)])
    m.X[3, 3] = True
    m.stats = {"r": {"kelp_columns": 1, "seagrass_columns": 0}, "q": {"kelp_columns": 0, "seagrass_columns": 0}}
    m.names = ["r", "q"]
    SF.lines(m)
    SF.checks(m)
    assert any("exclusion" in p for p in m.problems)
    assert any("q got nothing" in p for p in m.problems)


def test_checks_pass_a_clean_model():
    m = fake_model(kelp=[(3, 3, 40, 50)], grass=[(5, 5, 55, True)])
    SF.lines(m)
    SF.checks(m)
    assert m.problems == []


# ------------------------------------------------------------------ helpers and the writer

def test_dilate_matches_a_brute_force_square():
    rng = np.random.default_rng(4)
    a = rng.random((40, 40)) < 0.03
    got = SF.dilate(a, 3)
    want = np.zeros_like(a)
    for z, x in np.argwhere(a):
        want[max(0, z - 3):z + 4, max(0, x - 3):x + 4] = True
    assert (got == want).all()


def _brute_distance(land, x, z):
    zz, xx = np.nonzero(land)
    return float(np.sqrt(((xx - x) ** 2 + (zz - z) ** 2).min()))


def test_exact_distance_matches_a_brute_force_search():
    rng = np.random.default_rng(7)
    land = rng.random((96, 96)) < 0.004
    land[40, 3] = True
    gz = SF.column_distance(land, 1000)
    pts = rng.integers(0, 96, size=(300, 2))
    got = SF.exact_distance(gz, pts[:, 0], pts[:, 1], 140)
    want = [_brute_distance(land, x, z) for x, z in pts]
    assert np.allclose(got, want)


def test_the_coarse_bounds_hold_the_exact_distance():
    """the interval bounds() gives round the 4-block chamfer guess always holds the exact distance: the property the
    builder relies on to skip the exact search where no rule's threshold falls inside it."""
    s = spec()
    c = int(s["land_distance"]["coarse_blocks"])
    rng = np.random.default_rng(11)
    N = 160
    land = np.zeros((N, N), bool)
    for _ in range(6):
        z, x = rng.integers(0, N, 2)
        land[z:z + 3, x:x + 2] = True
    H = np.where(land, 70, 40).astype(np.int16)
    DL = SF.land_distance(H, SEA, s)
    gz = SF.column_distance(land, 1000)
    zz, xx = np.mgrid[0:N, 0:N]
    exact = SF.exact_distance(gz, xx.ravel(), zz.ravel(), 400).reshape(N, N)
    dl = DL[np.ix_(np.arange(N) // c, np.arange(N) // c)]
    lo, hi = SF.bounds(dl, s)
    assert (lo <= exact + 1e-9).all() and (exact <= hi + 1e-9).all()


def test_rects_finds_every_pacifidlog_walk():
    doc = json.loads((ROOT / "data" / "sea_town.json").read_text(encoding="utf-8"))
    got = set(SF.rects(doc, []))
    for w in doc["walks"]:
        assert tuple(w["rect"]) in got, w["id"]


def test_data_frostwater_carries_both_frozen_rules_from_regions_json():
    s = spec()["regions"]["frostwater_shelf"]
    doc = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    rules = " | ".join(next(r for r in doc["marine_regions"] if r["id"] == "frostwater_shelf")["biomes"]["rules"])
    assert "deep_frozen_ocean: north of z%d" % s["deep_frozen"]["north_of_z"] in rules
    assert "at or below y%d" % s["deep_frozen"]["at_or_below_y"] in rules
    assert "frozen_ocean: north of z%d, %d or more blocks from land" % (s["frozen"]["north_of_z"],
                                                                      s["frozen"]["from_land_blocks"]) in rules


def test_write_tiles_functions_by_128_and_each_passes_the_limits(tmp_path):
    grass = [(x, z, 50, False) for z in (5, 130) for x in range(0, 300)]
    m = fake_model(grass=grass, N=512)
    SF.lines(m)
    out = tmp_path / "cobblers_sea_floor"
    order = SF.write(m, out)
    fn = out / "data" / "cobblers" / "function" / "sea_floor"
    assert (out / "pack.mcmeta").is_file()
    assert (fn / "index.txt").read_text(encoding="utf-8").split() == order
    assert len(order) == 6                      # three 128 tiles along x, in two tile rows
    for name in order:
        body = (fn / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines()
        assert FL.check_lines(body, name) == []
        tx, tz = (int(v) for v in name.split("_")[1:3])
        for ln in body:
            g = FILL.match(ln)
            if g:
                assert int(g.group(1)) // 128 == tx and int(g.group(4)) // 128 == tx
                assert int(g.group(3)) // 128 == tz


# ------------------------------------------------------------------ the wiring

def test_reapply_runs_the_pack_after_sea_life():
    import reapply
    assert "cobblers_sea_floor" in reapply.SERVER_PACKS
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.index('("R9SL"') < src.index('("R9SF"')
    assert 'add("sea_floor:build", "sea_floor.py", "build"' in src
    assert src.index('add("sea_life:build"') < src.index('add("sea_floor:build"')


# ------------------------------------------------------------------ the built pack, if present

BUILT = ROOT / "build" / "datapacks" / "cobblers_sea_floor" / "data" / "cobblers" / "function" / "sea_floor"


@pytest.mark.skipif(not (BUILT / "index.txt").is_file(), reason="the pack is not built here")
def test_built_pack_writes_only_water_plants_under_the_rule():
    s = spec()
    tmax = SEA - int(s["kelp"]["max_top_below_surface"])
    allowed = {"minecraft:kelp_plant", "minecraft:kelp[age=25]", "minecraft:seagrass",
               "minecraft:tall_seagrass[half=lower]", "minecraft:tall_seagrass[half=upper]"}
    n = 0
    for name in (BUILT / "index.txt").read_text(encoding="utf-8").split():
        for ln in (BUILT / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines():
            if not ln or ln.startswith("#") or ln.startswith("forceload "):
                continue
            g = FILL.match(ln)
            assert g, ln
            assert g.group(7) in allowed, ln
            y1 = int(g.group(5))
            if g.group(7).startswith("minecraft:kelp"):
                assert y1 <= tmax, ln
            assert y1 <= SEA - 1, ln
            n += 1
    assert n > 0
