"""tools/lake_life_audit.py: the independent audit of the lake skin and hooks (cobblers_lake_life).

Two halves. The synthetic half builds a tiny lake whose every number is computable by hand (a 20 x 20 basin at level
y100: a 1-deep shelf at x0-4, a 5-deep drop-off band at x5-9, a 20-deep floor at x10-19, dry ground at y100 round it)
and a hand-written pack, and proves each check fires on the fault it names and stays quiet on the correct case. The
real half (marked slow) runs the audit on the pack tools/lake_life.py built, over the canonical heightmap; it skips
when either is absent.

What none of this covers: kelp, seagrass and lanterns holding in a lake in game (proof P6), a light seen from the
surface (P4), and any block a world holds that is not the heightmap's (validity is not runtime behaviour).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import lake_life_audit as LA       # noqa: E402
import water_life_replay as R      # noqa: E402
import water_mask as WM            # noqa: E402

LEVEL = 100


class FakeGround:
    """The synthetic bed: shelf 1 deep at x0-4, drop-off 5 deep at x5-9, floor 20 deep at x10-19, dry y100 outside."""

    def __call__(self, x, z):
        if 0 <= x <= 19 and 0 <= z <= 19:
            return 99 if x <= 4 else (95 if x <= 9 else 80)
        return 100

    def box(self, x0, z0, x1, z1):
        import numpy as np
        return np.array([[self(x, z) for x in range(x0, x1 + 1)] for z in range(z0, z1 + 1)])


BODIES = {"lake": {"level_y": LEVEL, "basin": [[(0, 0), (20, 0), (20, 20), (0, 20)]]}}

SPEC = {
    "zones": {"shelf_depths": [1, 2], "drop_from_depth": 3},
    "skin": {"kelp": {"top_below_surface": 3}, "drowned_trees": {"trunk": "minecraft:stripped_dark_oak_log"}},
    "exclusions": {"portal_clearance_blocks": 6, "mouth_clearance_blocks": 2, "placement_margin_blocks": 16},
    "lights": {"blocks": ["lantern", "soul_lantern", "sea_pickle", "glow_lichen"], "within_blocks": 8},
    "palette": {"weight": "minecraft:polished_andesite", "chain": "minecraft:chain", "case": "minecraft:barrel",
                "hull": "minecraft:spruce_planks", "soul_lantern": "minecraft:soul_lantern"},
    "hooks": [],
}
SHAPE = {"lakes": {"bodies": [{"id": "lake", "drop_depth": 10}]}}
LAKE_BED = ["minecraft:sand", "minecraft:gravel", "minecraft:mud", "minecraft:clay", "minecraft:cobblestone"]


def ctx(**kw):
    spec = json.loads(json.dumps(SPEC))
    spec.update(kw.pop("spec", {}))
    t = R.Terrain(FakeGround(), 62, BODIES)
    return LA.Ctx(t, spec, SHAPE, **kw)


def pack(tmp_path, functions, index=None, tag=LAKE_BED):
    fn = tmp_path.joinpath(*LA.FN)
    fn.mkdir(parents=True)
    for name, lines in functions.items():
        body = ["# chunks-loaded-by: the test"] + list(lines)        # tools/function_limits.py's declared form
        (fn / (name + ".mcfunction")).write_text("\n".join(body) + "\n", encoding="utf-8")
    (fn / "index.txt").write_text("\n".join(index if index is not None else functions) + "\n", encoding="utf-8")
    td = tmp_path / "data" / "cobblers" / "tags" / "block"
    td.mkdir(parents=True)
    (td / "lake_bed.json").write_text(json.dumps({"values": tag}), encoding="utf-8")
    return tmp_path


def run(tmp_path, functions, c=None, **kw):
    res = LA.audit(c or ctx(), pack(tmp_path, functions, **kw))
    return res, res["problems"]


# a correct skin: a seagrass on the shelf, a kelp column in the drop-off band topped 3 under the surface, mud on the
# floor's top bed block, and a lily pad on the shelf's surface
GOOD = {
    "1bed_0_0": ["fill 12 80 5 12 80 5 minecraft:mud replace #cobblers:lake_bed"],
    "2plants_0_0": [
        "fill 2 100 2 2 100 2 minecraft:seagrass replace minecraft:water",
        "fill 6 96 6 6 96 6 minecraft:kelp_plant replace minecraft:water",
        "fill 6 97 6 6 97 6 minecraft:kelp[age=25] replace minecraft:water",
        "fill 3 101 3 3 101 3 minecraft:lily_pad replace minecraft:air",
    ],
}


# --------------------------------------------------------------------------------------------- the machinery


def test_scanline_basin_raster_matches_water_masks_point_test():
    # Without it, the audit's lake columns could disagree with water_mask's painting rule on a concave basin.
    ring = [(0, 0), (12, 0), (12, 10), (6, 4), (0, 10)]
    m = R.raster_polygons([ring], -1, -1, 13, 11)
    for z in range(-1, 12):
        for x in range(-1, 14):
            assert bool(m[z + 1, x + 1]) == WM.in_polygons([ring], x, z), (x, z)


def test_an_unmodelled_command_fails_the_parse():
    # Without it, a pack could write blocks through `clone` or `place` and the audit would never see them.
    with pytest.raises(R.ReplayError):
        R.parse_line("clone 0 0 0 1 1 1 5 5 5", "f", 1)


def test_a_function_missing_from_the_index_is_reported(tmp_path):
    # Without it, a function on disk that never runs would pass unseen, or one the index omits would be unaudited.
    _, P = run(tmp_path, {"2plants_0_0": GOOD["2plants_0_0"], "2plants_1_0": []}, index=["2plants_0_0"])
    assert any("not in the index" in p for p in P["parse"])


def test_a_filtered_write_lands_only_where_the_cell_holds_what_the_filter_names():
    # Without it, a `replace minecraft:water` into ground would be counted as kelp that exists.
    W = R.World(R.Terrain(FakeGround(), 62, BODIES))
    R.replay(W, [("2plants_0_0", [R.parse_line("fill 6 95 6 6 96 6 minecraft:kelp_plant replace minecraft:water")])])
    assert (6, 96, 6) in W.w and (6, 95, 6) not in W.w        # y95 is the bed (ground), y96 the first water
    assert len(W.dead) == 1


def test_foreign_overlap_separates_shared_cells_sealed_roofs_and_open_columns():
    # Without it, a lake write over a legendary's open shaft would read the same as one over its sealed chamber.
    theirs = {(0, 0): [(40, 50, "minecraft:stone")], (1, 0): [(40, 60, "minecraft:water")],
              (2, 0): [(40, 50, "minecraft:stone")]}
    cells, sealed, open_ = R.foreign_overlap({(0, 70, 0), (1, 70, 0), (2, 45, 0)}, theirs)
    assert sealed == [(0, 0)] and open_ == [(1, 0)] and cells == [(2, 45, 0)]


# ---------------------------------------------------------------------------------------------------- checks


def test_a_correct_skin_passes_every_check(tmp_path):
    # Without it, a check that fails on everything would look like a check that works.
    res, P = run(tmp_path, GOOD)
    assert {k: v for k, v in P.items() if v} == {}
    assert res["kelp"]["kelp_tops"] == 1 and res["silt"]["bed_writes"] == 1


def test_a_kelp_top_within_two_of_the_surface_fails(tmp_path):
    # Without it, kelp could reach the surface (WATER_LIFE 1: never within 2 of it, i.e. at most level - 3).
    f = {"2plants_0_0": ["fill 6 96 6 6 97 6 minecraft:kelp_plant replace minecraft:water",
                         "fill 6 98 6 6 98 6 minecraft:kelp[age=25] replace minecraft:water"]}
    _, P = run(tmp_path, f)
    assert any("2 under the surface" in p for p in P["kelp"])


def test_a_kelp_top_that_still_grows_fails(tmp_path):
    # Without it, kelp below level - 3 at any age but 25 would grow up to the surface after the build.
    f = {"2plants_0_0": ["fill 6 96 6 6 96 6 minecraft:kelp[age=3] replace minecraft:water"]}
    _, P = run(tmp_path, f)
    assert any("age 3" in p for p in P["kelp"])


def test_the_spec_floor_for_the_kelp_gap_is_enforced_on_the_data(tmp_path):
    # Without it, loosening data/lake_life.json's top_below_surface to 2 would pass silently.
    _, P = run(tmp_path, GOOD, c=ctx(spec={"skin": {"kelp": {"top_below_surface": 2},
                                                    "drowned_trees": {"trunk": "x"}}}))
    assert any("never within 2" in p for p in P["kelp"])


def test_seagrass_with_nothing_under_it_fails(tmp_path):
    # Without it, a plant written a block above the bed would float (and break) unseen.
    f = {"2plants_0_0": ["fill 6 97 6 6 97 6 minecraft:seagrass replace minecraft:water"]}
    _, P = run(tmp_path, f)
    assert any("seagrass" in p and "on minecraft:water" in p for p in P["plants"])


def test_a_kelp_stem_with_no_head_fails(tmp_path):
    # Without it, a kelp_plant left as the top would turn into a growing head in game.
    f = {"2plants_0_0": ["fill 6 96 6 6 96 6 minecraft:kelp_plant replace minecraft:water"]}
    _, P = run(tmp_path, f)
    assert any("turns into a growing head" in p for p in P["plants"])


def test_a_lily_pad_off_the_surface_fails(tmp_path):
    # Without it, a lily pad on the bank or above another block would pass.
    f = {"2plants_0_0": ["fill 30 101 30 30 101 30 minecraft:lily_pad replace minecraft:air"]}
    _, P = run(tmp_path, f)
    assert any("lily_pad" in p for p in P["plants"])


def test_silt_below_the_top_bed_block_fails(tmp_path):
    # Without it, a silt write could cut into the bed (a column changing height) and pass.
    f = {"1bed_0_0": ["fill 12 79 5 12 79 5 minecraft:mud replace #cobblers:lake_bed"]}
    _, P = run(tmp_path, f)
    assert any("not the top bed block" in p for p in P["silt"])


def test_a_lake_bed_tag_holding_a_non_full_block_fails(tmp_path):
    # Without it, the bed filter could replace a slab or a plant, changing a column's top.
    _, P = run(tmp_path, GOOD, tag=LAKE_BED + ["minecraft:oak_slab"])
    assert any("oak_slab" in p for p in P["silt"])


def test_mud_in_the_drop_off_band_is_out_of_zone(tmp_path):
    # Without it, silt could land on the drop-off (or scree on the floor) against WATER_LIFE 1's zone table.
    f = {"1bed_0_0": ["fill 6 95 6 6 95 6 minecraft:mud replace #cobblers:lake_bed",
                      "fill 12 80 5 12 80 5 minecraft:gravel replace #cobblers:lake_bed"]}
    _, P = run(tmp_path, f)
    text = " ".join(P["zones"])
    assert "minecraft:mud" in text and "minecraft:gravel" in text


def test_a_write_away_from_every_lake_and_bank_fails(tmp_path):
    # Without it, the pack could write anywhere on the map.
    f = {"3structure_0_0": ["fill 40 101 40 40 101 40 minecraft:stone replace minecraft:air"]}
    _, P = run(tmp_path, f)
    assert any("no lake column" in p for p in P["place"])


def test_a_write_inside_a_dive_portals_clearance_fails_and_one_outside_passes(tmp_path):
    # Without it, a boulder could block a dive arch or its line down (apron 5 by 5 + portal_clearance_blocks).
    c = ctx(portals=[("dive_test", (15, 15))])
    f_in = {"3structure_0_0": ["fill 7 96 15 7 96 15 minecraft:stone replace minecraft:water"]}       # 8 from it
    f_out = {"3structure_0_0": ["fill 6 96 15 6 96 15 minecraft:stone replace minecraft:water"]}      # 9 from it
    _, P = run(tmp_path / "a", f_in, c=c)
    assert any("dive_test" in p for p in P["clear"])
    _, P = run(tmp_path / "b", f_out, c=c)
    assert not P["clear"]


def test_skin_inside_a_legendarys_spawn_free_zone_fails_but_a_hook_there_passes(tmp_path):
    # Without it, the skin could crowd a grotto, or the trio's dressing (the hooks) would be refused where it belongs.
    leg = [{"id": "mesprit", "mouth": None, "spawn_free_zone": [10, 10, 19, 19]}]
    _, P = run(tmp_path / "a", GOOD, c=ctx(legendaries=leg))
    assert not any("spawn_free_zone" in p for p in P["clear"])      # GOOD is outside it
    f = {"1bed_0_0": ["fill 12 80 12 12 80 12 minecraft:mud replace #cobblers:lake_bed"],
         "4hooks_0_0": ["fill 14 81 14 14 81 14 minecraft:stone replace minecraft:water"]}
    _, P = run(tmp_path / "b", f, c=ctx(legendaries=leg))
    assert len([p for p in P["clear"] if "spawn_free_zone" in p]) == 1
    assert "1 write columns" in P["clear"][0]


def test_a_light_block_or_a_bubble_column_maker_fails(tmp_path):
    # Without it, a bubble column (an air source) or an invisible light could be written (WATER_LIFE Departures).
    f = {"5lights_0_0": ["fill 12 81 5 12 81 5 minecraft:magma_block replace minecraft:water",
                         "fill 12 90 5 12 90 5 minecraft:light replace minecraft:water"]}
    _, P = run(tmp_path, f)
    text = " ".join(P["blocks"])
    assert "minecraft:magma_block" in text and "minecraft:light" in text


def test_a_door_under_water_is_a_dry_cell(tmp_path):
    # Without it, a block that keeps water out of its cell would give a diver a free breath.
    f = {"4hooks_0_0": ["fill 12 81 5 12 81 5 minecraft:oak_door[half=lower] replace minecraft:water"]}
    _, P = run(tmp_path, f)
    assert any("dry cell" in p for p in P["blocks"])


def test_a_hook_with_no_light_within_eight_fails(tmp_path):
    # Without it, a hook could be built that nobody sees from the surface (WATER_BUILD_PLAN 4.5 item 2).
    hook = {"id": "h", "lake": "lake", "kind": "chained_lantern"}
    c = ctx(spec={"hooks": [hook]})
    far = {"4hooks_0_0": ["fill 15 81 15 15 90 15 minecraft:chain[axis=y,waterlogged=true] replace minecraft:water"],
           "5lights_0_0": ["fill 15 99 5 15 99 5 minecraft:lantern[waterlogged=true] replace minecraft:water"]}
    _, P = run(tmp_path / "a", far, c=c)
    assert any("no light within 8" in p for p in P["hooks"])
    near = {"4hooks_0_0": far["4hooks_0_0"],
            "5lights_0_0": ["fill 15 82 16 15 82 16 minecraft:lantern[waterlogged=true] replace minecraft:water"]}
    _, P = run(tmp_path / "b", near, c=c)
    assert not P["hooks"]


def test_a_hook_record_with_nothing_built_fails(tmp_path):
    # Without it, a hook the data promises could be silently missing.
    c = ctx(spec={"hooks": [{"id": "h", "lake": "lake", "kind": "skiff"}]})
    _, P = run(tmp_path, GOOD, c=c)
    assert any("no hook writes" in p for p in P["hooks"])


def test_a_painted_lake_with_no_skin_fails(tmp_path):
    # Without it, a lake the skin forgot would pass (WATER_BUILD_PLAN 3.5 item 11: nonempty per lake).
    _, P = run(tmp_path, {"5lights_0_0": ["fill 12 81 5 12 81 5 minecraft:lantern[waterlogged=true] "
                                          "replace minecraft:water"]})
    assert P["nonempty"] == ["lake: no skin write lands in it"]


def test_a_barrel_without_a_record_or_outside_its_trigger_fails(tmp_path):
    # Without it, a cache could be scenery with no reward, or a reward nobody can trigger.
    f = {"4hooks_0_0": ["fill 12 81 5 12 81 5 minecraft:barrel replace minecraft:water"]}
    _, P = run(tmp_path / "a", f)
    assert any("no data/rewards.json record" in p for p in P["cache"])
    rec = {"id": "lake_life_test", "container": {"at": [12, 81, 5]}, "trigger": {"min": [20, 81, 5], "max": [21, 82, 6]}}
    _, P = run(tmp_path / "b", f, c=ctx(rewards=[rec]))
    assert any("does not hold its barrel" in p for p in P["cache"])


def test_a_write_in_a_column_another_pack_leaves_open_fails(tmp_path):
    # Without it, the skin could land in a legendary's shaft or a portal's apron another pack carves.
    c = ctx(foreign={"cobblers_legendaries": {(12, 5): [(60, 80, "minecraft:water")]}})
    _, P = run(tmp_path, GOOD, c=c)
    assert any("cobblers_legendaries" in p for p in P["foreign"])


# ------------------------------------------------------------------------------------- the pack as built


@pytest.fixture(scope="module")
def real():
    from terrain import TerrainUnavailable
    if not LA.PACK.joinpath(*LA.FN).joinpath("index.txt").is_file():
        pytest.skip("build/datapacks/cobblers_lake_life is not built here (python tools/lake_life.py build)")
    try:
        c = LA.load_ctx()
    except (TerrainUnavailable, OSError) as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])
    return LA.audit(c)


REAL_CHECKS = ["parse", "place", "plants", "kelp", "zones", "silt", "clear", "blocks", "hooks", "cache", "nonempty",
               "foreign", "limits"]


@pytest.mark.slow
@pytest.mark.parametrize("check", REAL_CHECKS)
def test_the_built_lake_pack_passes(real, check):
    # Without it, a regression in tools/lake_life.py or its data would reach a world with only its own checks run.
    assert real["problems"][check] == []


@pytest.mark.slow
def test_the_built_lake_pack_skins_all_nine_painted_lakes(real):
    # Without it, the audit could pass on a pack that skips a lake (all nine painted bodies, measured 2026-10-02).
    assert len([k for k, v in real["nonempty"]["skin_writes_per_lake"].items() if v]) == 9
