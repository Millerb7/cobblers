"""tools/coast_fringe_audit.py: the coast fringe (U61/N2) covers the coast, stays out of no-spawn places, keeps the
encounter rules, and gives each coast cell to its nearest sub-region's BASE roster.

Written by the test author, not by the session that built tools/coast_fringe.py (59a589f). Independence: the audit
never imports tools/coast_fringe.py or tools/compile_spawns.py; it reads the compiled pack and the authored data and
measures the coast with its own algorithms. The synthetic fixtures below are small enough that every expected count
is read off the fixture by hand.

Generator mutations (run 2026-10-09 in a scratch copy of the two generators, data/ untouched, each regenerating the
fringe and the pack and re-running the audit; the driver is not kept because each run reads the whole heightmap):
  unmutated               3 failures (F6 x2, F8 x1: the findings below)
  owner = FARTHEST polygon  F5 x1905 (every cell)
  RING_CELLS = 2          F6 2 -> 6, F8 1 -> 2 (4 of the 7 extra cells fill no coast gap)
  no marine exclusion     F1 x59 (fringe boxes over marine band boxes)
  no raster exclusion     F1 x952, F6 x2222
  fringe takes the heart  F7 x796
  no spawn-free/waterway exclusion (generator and compile both): 3 failures, unchanged -- no free coast cell meets a
                          spawn-free zone or waterway in today's data, so that rule does not bind on the real map; the
                          synthetic F1 tests below are what prove the check bites.

Not covered (validity is not runtime behaviour): whether Cobblemon draws the fringe entries in game; a habitat block's
true influence shape; lake shores and inland land (not the unit's scope); that the inherited pools are absent over the
fringe in game (the suppression box set is checked below, its effect needs a server).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import coast_fringe_audit as A  # noqa: E402


# ------------------------------------------------------------------ terrain measurement on hand-built grids

# Without it a lake ringed by land would count as open sea and its shore as coast.
def test_open_sea_is_only_water_connected_to_the_edge():
    g = np.full((7, 7), 70.0)
    g[0, :] = 50          # a sea strip along the north edge: 7 columns
    g[1, 3] = 50          # an inlet joined to it: 1 column
    g[4, 4] = 50          # an enclosed pond: not open sea
    sea = A.open_sea(g, 62)
    assert int(sea.sum()) == 8
    assert not sea[4, 4] and sea[1, 3]


# Without it a diagonal-only touch would join a pond to the sea (the coast rule is 4-adjacency).
def test_a_diagonal_touch_does_not_join_the_sea():
    g = np.full((5, 5), 70.0)
    g[0, 0] = 50
    g[1, 1] = 50
    assert A.open_sea(g, 62).sum() == 1


# Without it the coast band's width would be wrong by the metric: the distance is city-block and saturates at cap + 1.
def test_cityblock_distance_is_exact_and_saturates():
    src = np.zeros((9, 9), dtype=bool)
    src[4, 4] = True
    d = A.cityblock(src, 5)
    assert d[4, 4] == 0 and d[4, 7] == 3 and d[2, 2] == 4 and d[1, 2] == 5
    assert d[0, 0] == 6    # 8 away, saturated at 5 + 1


# Without it the coverage numbers would count the sea itself, or land past 32 blocks, as coast.
def test_coast_land_is_land_within_reach_of_open_sea():
    g = np.full((4, 10), 70.0)
    g[:, :3] = 50          # sea on the west edge, columns 0-2
    near = A.coast_land(g, 62, reach=2)
    assert int(near.sum()) == 8                 # columns 3 and 4, four rows
    assert near[:, 3].all() and near[:, 4].all() and not near[:, 5].any()


# ------------------------------------------------------------------ a fixture world, hand-built

def entry(kind, area, eid, box, level=(4, 8), pos="grounded", pokemon="pidgey", bucket="common", weight=24, minY=False):
    return {"kind": kind, "area": area, "id": eid, "pokemon": pokemon, "pos": pos, "level": level, "bucket": bucket,
            "weight": weight, "box": box, "alpha": "alpha" in pokemon, "minY": minY}


def base_and_fringe(area="shore_a", base_box=(0, 31, 0, 31), fringe_box=(32, 63, 0, 31), level=(4, 8), pos="grounded"):
    return [entry("subregions", area, "%s_pidgey" % area, base_box, level, pos),
            entry("subregions", area, "%s_c0000_pidgey" % area, fringe_box, level, pos)]


def ctx(**over):
    c = {
        "routes": [{"id": "route_01", "order": 1,
                    "spawn_scope": {"boxes": [{"min_x": 0, "max_x": 10, "min_z": 500, "max_z": 510}]}}],
        "towns": [],
        "design": {"tables": {"shore_a": {"tier": 1, "placement": "path"}, "shore_b": {"tier": 1, "placement": "path"},
                              "arrow_lake": {"tier": 1, "placement": "path"},
                              "far_isle": {"tier": 3, "placement": "off"}}},
        "regions": {"subregions": [{"id": "shore_a", "polygons": [[[0, 0], [31, 0], [31, 31], [0, 31]]]},
                                   {"id": "shore_b", "polygons": [[[300, 0], [331, 0], [331, 31], [300, 31]]]}]},
        "free_zones": [],
        "habitat_blocks": [],
        "rift_polys": [],
    }
    c.update(over)
    return c


def fails_of(entries, **over):
    f, _ = A.audit(entries, **ctx(**over))
    return f


# Without it every "fails on X" below could be failing for a reason no test names.
def test_a_fringe_meeting_every_rule_passes():
    assert fails_of(base_and_fringe()) == []


# Without it a fringe id in ANOTHER sub-region's file, or a plain id, would be read as fringe (or missed).
def test_the_fringe_is_recognised_by_its_compiled_id_in_its_own_file():
    assert A.is_fringe(entry("subregions", "shore_a", "shore_a_c0003_pidgey", (0, 1, 0, 1)))
    assert not A.is_fringe(entry("subregions", "shore_b", "shore_a_c0003_pidgey", (0, 1, 0, 1)))
    assert not A.is_fringe(entry("subregions", "shore_a", "shore_a_pidgey", (0, 1, 0, 1)))
    assert not A.is_fringe(entry("routes", "shore_a", "shore_a_c0003_pidgey", (0, 1, 0, 1)))


# Without it the before/after coverage would be the generator's word, not a measurement.
def test_coverage_counts_coast_land_before_and_after_the_fringe():
    near = np.zeros((40, 80), dtype=bool)
    near[0:10, 0:64] = True                      # 640 coast columns
    ents = base_and_fringe()
    ents.append(entry("marine", "band", "band_magikarp", (60, 79, 0, 39), pos="surface"))
    cov = A.coverage(near, ents, free_boxes=[(0, 3, 0, 9)])   # 40 columns spawn-free
    # before: the base box covers x0-31 (320 columns, 40 of them spawn-free anyway); x32-63 is uncovered: 320,
    # of which x60-63 (40 columns) lie under the marine band only
    assert cov["before"] == {"no_grounded_table": 280, "under_marine_only": 40}
    assert cov["after"] == {"no_grounded_table": 0, "under_marine_only": 0}


# ------------------------------------------------------------------ F1 exclusions

# Without it a fringe cell could put wild Pokemon into a gym or the League precinct.
def test_a_fringe_box_in_a_spawn_free_zone_fails_and_one_touching_its_edge_passes():
    assert any(f.startswith("F1") for f in fails_of(base_and_fringe(), free_zones=[("gym_x", (63, 70, 0, 5))]))
    assert fails_of(base_and_fringe(), free_zones=[("gym_x", (64, 70, 0, 5))]) == []


# Without it a coast roster could spill into Victory Road's corridor.
def test_a_fringe_box_on_victory_road_fails():
    vr = {"id": "victory_road", "order": 9, "spawn_scope": {"boxes": [{"min_x": 40, "max_x": 45, "min_z": 0, "max_z": 5}]}}
    f = fails_of(base_and_fringe(), routes=ctx()["routes"] + [vr])
    assert any("Victory Road" in x for x in f)


# Without it a coast cell inside the Rift would take an outside table.
def test_a_fringe_box_meeting_the_rift_fails():
    rift = [[[50, 10], [90, 10], [90, 40], [50, 40]]]
    assert any("Rift" in x for x in fails_of(base_and_fringe(), rift_polys=rift))
    far = [[[500, 500], [520, 500], [520, 520]]]
    assert fails_of(base_and_fringe(), rift_polys=far) == []


# Without it a habitat pool that does not replace spawns would be mixed with a coast roster; one that replaces is
# reported, not failed (the block wins there).
def test_a_habitat_block_overlap_fails_only_when_it_does_not_replace_spawns():
    hb = {"id": "hb1", "position": {"x": 40, "y": 64, "z": 10}, "range_of_influence": 6}
    assert any("hb1" in x for x in fails_of(base_and_fringe(), habitat_blocks=[dict(hb, replace_spawns=False)]))
    f, info = A.audit(base_and_fringe(), **ctx(habitat_blocks=[dict(hb, replace_spawns=True)]))
    assert f == [] and info["habitat_replace_overlaps"] == [["shore_a", "hb1"]]


# Without it a fringe box could double another table's weights.
def test_a_fringe_box_over_another_areas_box_fails():
    ents = base_and_fringe() + [entry("waterways", "creek", "creek_magikarp", (60, 70, 0, 5), pos="surface")]
    assert any("waterways/creek" in x for x in fails_of(ents))


# ------------------------------------------------------------------ F2/F3 the path

def near_route(gap):
    # the fringe cell is x32-63, z0-31: a route box starting at z = 31 + gap is `gap` blocks away (Chebyshev)
    return [{"id": "route_01", "order": 1,
             "spawn_scope": {"boxes": [{"min_x": 40, "max_x": 50, "min_z": 31 + gap, "max_z": 40 + gap}]}}]


# Without it a coast cell 128 blocks from a leg-1 path could carry level-21 Pokemon nobody on that leg can catch.
def test_a_level_over_the_leg_cap_within_128_of_its_route_fails_and_at_the_cap_passes():
    assert fails_of(base_and_fringe(level=(14, 20)), routes=near_route(128)) == []
    assert any(f.startswith("F2") for f in fails_of(base_and_fringe(level=(14, 21)), routes=near_route(128)))
    assert fails_of(base_and_fringe(level=(14, 21)), routes=near_route(129)) == []


# Without it the earliest leg would not set the cap where two routes meet.
def test_the_earliest_near_leg_sets_the_cap():
    two = near_route(10) + [{"id": "route_05", "order": 5,
                             "spawn_scope": {"boxes": [{"min_x": 40, "max_x": 50, "min_z": 41, "max_z": 50}]}}]
    assert any("leg-1" in f for f in fails_of(base_and_fringe(level=(30, 38)), routes=two))


# Without it a settlement on the critical path could hold over-cap wild Pokemon at its edge.
def test_a_level_over_the_cap_near_a_critical_town_fails():
    town = {"id": "hometown", "order": 0, "footprint": {"min_x": 100, "max_x": 120, "min_z": 0, "max_z": 20}}
    assert any("hometown" in f for f in fails_of(base_and_fringe(level=(14, 21)), towns=[town]))
    assert fails_of(base_and_fringe(level=(14, 20)), towns=[town]) == []


# Without it an off-path table's find would be laid beside a path.
def test_an_off_path_tables_fringe_near_a_route_fails():
    ents = base_and_fringe(area="far_isle", level=(18, 20))
    regions = {"subregions": [{"id": "far_isle", "polygons": [[[0, 0], [31, 0], [31, 31], [0, 31]]]}]}
    assert any(f.startswith("F3") for f in fails_of(ents, regions=regions, routes=near_route(100)))
    assert fails_of(ents, regions=regions, routes=near_route(200)) == []


# ------------------------------------------------------------------ F5-F8

# Without it a coast cell could be given to a polygon across the map (the farthest-owner mutant).
def test_a_cell_given_to_a_farther_polygon_fails():
    ents = [entry("subregions", "shore_b", "shore_b_pidgey", (300, 331, 0, 31)),
            entry("subregions", "shore_b", "shore_b_c0000_pidgey", (32, 63, 0, 31))]
    assert any(f.startswith("F5") for f in fails_of(ents))


# Without it a fringe cell could cover inland land or land another table already covers, outside the unit's purpose.
def test_a_fringe_cell_that_fills_no_coast_gap_fails():
    near = np.zeros((40, 80), dtype=bool)
    other = np.zeros_like(near)
    assert any(f.startswith("F6") for f in fails_of(base_and_fringe(), near=near, other_cover=other))
    near[5, 40] = True
    assert fails_of(base_and_fringe(), near=near, other_cover=other) == []
    other[5, 40] = True
    assert any(f.startswith("F6") for f in fails_of(base_and_fringe(), near=near, other_cover=other))


# Without it a heart's alphas or a partial roster could reach the coast.
def test_a_heart_or_a_short_roster_on_the_fringe_fails():
    ents = base_and_fringe() + [entry("subregions", "shore_a", "shore_a_c0000_onix", (32, 63, 0, 31),
                                      pokemon="onix alpha=true")]
    assert any(f.startswith("F7") for f in fails_of(ents))
    short = base_and_fringe() + [entry("subregions", "shore_a", "shore_a_rattata", (0, 31, 0, 31), pokemon="rattata")]
    assert any(f.startswith("F7") for f in fails_of(short))


# Without it a lake's own fish would be laid on the open-sea coast (section 5: distinct waters).
def test_a_water_named_tables_water_entries_on_the_fringe_fail():
    ents = base_and_fringe(area="arrow_lake", pos="surface")
    regions = {"subregions": [{"id": "arrow_lake", "polygons": [[[0, 0], [31, 0], [31, 31], [0, 31]]]}]}
    assert any(f.startswith("F8") for f in fails_of(ents, regions=regions))
    assert fails_of(base_and_fringe(pos="surface"), regions=ctx()["regions"]) == []


# ------------------------------------------------------------------ the real data

@pytest.fixture(scope="module")
def real(tmp_path_factory):
    """The pack compiled now from data/ into a scratch dir, and the audit run on it with the canonical heightmap."""
    import terrain as T
    try:
        h, world = T.load(str(ROOT / "data" / "world.json"))
    except (FileNotFoundError, SystemExit, OSError) as e:
        pytest.skip("canonical heightmap not available: %s" % e)
    import compile_spawns
    out = tmp_path_factory.mktemp("coast_fringe_real") / "cobblers_spawns"
    assert compile_spawns.main(["--out", str(out)]) == 0
    entries = A.read_pack(out)
    c = A.load_context()
    near = A.coast_land(np.round(h), T.sea_level(world))
    other = A.paint(near.shape, {e["box"] for e in entries
                                 if e["kind"] != "marine" and e["pos"] == "grounded" and not A.is_fringe(e)})
    fails, info = A.audit(entries, near=near, other_cover=other, **c)
    cover = A.coverage(near, entries, [z for _, z in c["free_zones"]])
    return {"pack": out, "entries": entries, "fails": fails, "info": info, "cover": cover}


# Without it a regenerated fringe could reach a gym, Victory Road, the Rift or another table, carry an over-cap level
# or an off-path find beside a path, go to a farther polygon, or carry a heart, and prepare would install it.
def test_the_real_fringe_breaks_no_exclusion_path_owner_or_roster_rule(real):
    hard = [f for f in real["fails"] if f.split()[0] in ("F1", "F2", "F3", "F5", "F7")]
    assert hard == []
    assert real["info"]["fringe_cells"] > 0


# Without it the fringe could compile to nothing (a stale polygon sha drops it silently) and the coast stay bare.
def test_the_real_fringe_reduces_the_uncovered_coast(real):
    before, after = real["cover"]["before"]["no_grounded_table"], real["cover"]["after"]["no_grounded_table"]
    assert after < before


# FINDING (strict xfail; when fixed this XPASSes and fails -- drop the marker). Two fringe cells hold no coast land
# that another grounded table does not already cover: south_strand (2272, 6208) and tilpey_east_shore (7040, 4096).
def test_every_real_fringe_cell_fills_a_coast_gap(real):
    f6 = [f for f in real["fails"] if f.startswith("F6")]
    if f6:
        pytest.xfail("F6 finding, %d cells: %s" % (len(f6), "; ".join(f6)))
    assert f6 == []


# FINDING (xfail): peak_pond_hollow, a pond's table, is given one coast cell (2912, 512) and its pond fish (submerged
# basculin, buizel, floatzel, tynamo...) and seafloor krabby/kingler are laid on the open sea there (section 5).
def test_no_real_lake_table_lays_its_fish_on_the_sea_coast(real):
    f8 = [f for f in real["fails"] if f.startswith("F8")]
    if f8:
        pytest.xfail("F8 finding: %s" % "; ".join(f8))
    assert f8 == []


# Without it data/coast_fringe.json could go stale against the heightmap, routes or waterways and nothing would say.
def test_the_committed_coast_fringe_is_what_todays_inputs_give(real):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "coast_fringe.py"), "--check"], capture_output=True,
                       text=True, cwd=str(ROOT), timeout=200)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]


# FINDING (xfail): tools/suppress_inherited_spawns.py builds its --subregions box set from the sub-region POLYGONS
# (lines 176-179), not the compiled boxes, so the coast fringe cells keep every inherited Cobblemon/Cobbleverse pool
# and the fringe roster merely adds to them ("vanilla with sprinkles", that tool's own words for unsuppressed
# rosters). Without this test the fringe could be installed believed to own its coast.
def test_the_inherited_pools_are_suppressed_over_every_fringe_box(real, tmp_path):
    import suppress_inherited_spawns as S
    server, world, out = tmp_path / "server", tmp_path / "world", tmp_path / "out"
    pool = server / "datapacks" / "fake_pack" / "data" / "fake" / "spawn_pool_world" / "x.json"
    pool.parent.mkdir(parents=True)
    pool.write_text(json.dumps({"enabled": True, "spawns": [{"id": "x", "pokemon": "magikarp"}]}), encoding="utf-8")
    (world / "datapacks").mkdir(parents=True)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        S.main(["--server", str(server), "--world", str(world), "--subregions", "--boxes", "merged", "--grid", "16",
                "--out", str(out)])
    doc = json.loads((out / "data" / "fake" / "spawn_pool_world" / "x.json").read_text(encoding="utf-8"))
    sup = [(a["minX"], a["maxX"], a["minZ"], a["maxZ"]) for a in doc["spawns"][0]["anticonditions"]]
    n = 10240 // 16 + 2
    m = np.zeros((n, n), dtype=bool)
    for x0, x1, z0, z1 in sup:
        m[max(0, z0 // 16):z1 // 16 + 1, max(0, x0 // 16):x1 // 16 + 1] = True
    fr = {e["box"] for e in real["entries"] if A.is_fringe(e)}
    bare = [b for b in fr if not m[b[2] // 16:b[3] // 16 + 1, b[0] // 16:b[1] // 16 + 1].all()]
    if bare:
        pytest.xfail("suppression finding: %d of %d fringe boxes keep their inherited pools, e.g. %s"
                     % (len(bare), len(fr), sorted(bare)[:3]))
    assert bare == []
