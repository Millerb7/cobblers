"""tools/far_south.py's own guards, and the measurement it was sited by (tools/south_density.py).

These are the BUILDER'S tests, written by the agent that built the far south (2026-10-04): they prove that the
generator's fail-closed guards bite (each mutation edits a copy of the record and must make the build refuse) and that
the shipped record builds. They are NOT the independent audit: that is owed (data/far_south.json audit_checklist), and
whoever writes it must not import tools/far_south.py to derive anything.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import far_south as FS  # noqa: E402

pytest.importorskip("numpy")


@pytest.fixture(scope="module")
def g():
    import ground as G
    try:
        return G.load()
    except Exception as e:  # the canonical heightmap lives outside the repo (data/notes/source_tree.md)
        pytest.skip("no canonical heightmap here: %s" % e)


@pytest.fixture(scope="module")
def doc():
    return FS.load()


@pytest.fixture(scope="module")
def built(doc, g):
    out, sites = FS.files(doc, g)
    return out, sites


def _site(d, rid):
    return next(r for r in d["residents"] if r["id"] == rid)


def _refused(d, g, needle):
    with pytest.raises(SystemExit) as e:
        FS.files(d, g)
    assert needle in str(e.value), str(e.value)[:600]


# ------------------------------------------------------------------ the shipped record


def test_the_shipped_record_builds_five_places_in_rows_f_to_h(doc, built):
    out, sites = built
    assert len(sites) == 5
    for r, s, extra, box in sites:
        assert box[1] >= doc["rules"]["south_of_z"], (r["id"], box)
        assert "data/cobblers/function/far_south/%s/build.mcfunction" % r["id"] in out


def test_every_place_stands_in_a_different_cell(doc):
    cells = [r["cell"] for r in doc["residents"]]
    assert len(cells) == len(set(cells)), cells


def test_each_resident_has_its_keeper_functions_and_a_keeper_line(doc, built):
    out, _ = built
    keeper = out["data/cobblers/function/far_south/keeper.mcfunction"]
    for r in doc["residents"]:
        pk = r.get("pokemon")
        if not pk:
            continue
        assert "data/cobblers/function/far_south/%s/keep.mcfunction" % pk["id"] in out, pk["id"]
        assert "far_south/%s/keep" % pk["id"] in keeper, pk["id"]
    assert json.loads(out["data/minecraft/tags/function/load.json"])["values"] == ["cobblers:far_south/load"]


def test_every_cache_has_an_items_hook_and_a_reward_that_gives_something(doc):
    rw = {r["id"]: r for r in json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))["rewards"]}
    n = 0
    for r in doc["residents"]:
        for c in r.get("caches") or []:
            n += 1
            assert c["items_hook"]["reward"] == c["reward"]
            assert rw[c["reward"]]["kind"] == "cache" and rw[c["reward"]]["contents"], c["reward"]
    assert n == 3


def test_the_steps_hold_build_and_release_each_site_and_r18fs_is_empty_while_all_are_gated(doc, g):
    steps = FS.placement_steps(doc, g)
    fns = [a for k, a in steps if k == "fn"]
    assert fns == ["cobblers:far_south/%s/build" % r["id"] for r in doc["residents"]]
    assert len(steps) == 4 * len(doc["residents"])
    assert all(r["pokemon"].get("appears_after") for r in doc["residents"] if r.get("pokemon"))
    assert FS.entity_steps(doc, g) == []


def test_reapply_runs_r9fs_before_r9e_and_r18fs_after_r18nr():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert text.index('"R9NR"') < text.index('"R9FS"') < text.index('("R9E"')
    assert text.index('"R18NR"') < text.index('"R18FS"')
    world_local = text[text.index("WORLD_LOCAL = ("):text.index("SPAWN_PACKS = (")]
    assert '"cobblers_far_south"' in world_local


# ------------------------------------------------------------------ the guards bite (each mutation must be refused)


def test_a_resident_over_its_tier_ceiling_is_refused(doc, g):
    d = copy.deepcopy(doc)
    _site(d, "glyph_ring")["pokemon"]["level"] = 61
    _refused(d, g, "ceiling")


def test_a_site_moved_onto_authored_ground_is_refused(doc, g):
    d = copy.deepcopy(doc)
    cistern = json.loads((ROOT / "data" / "dry_cistern.json").read_text(encoding="utf-8"))["chamber"]["centre"]
    _site(d, "four_chimneys")["site"]["centre"] = list(cistern)   # onto the Dry Cistern, read from its own record
    _refused(d, g, "authored in data/")


def test_a_site_north_of_row_f_is_refused(doc, g):
    d = copy.deepcopy(doc)
    _site(d, "stallion_kraal")["site"]["centre"] = [2808, 5100]
    _refused(d, g, "north of z 5120")


def test_a_site_in_the_keep_out_box_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["rules"]["keep_out_box"]["box"] = [2700, 5700, 2900, 5800]
    _refused(d, g, "keep-out box")


def test_a_spawn_condition_block_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["blocks"]["ids"].append("minecraft:sand")
    _site(d, "glass_garden")["pieces"][0]["palette"].append(["minecraft:sand", 5])
    _refused(d, g, "spawn-condition")


def test_a_recorded_anchor_the_heightmap_disagrees_with_is_refused(doc, g):
    d = copy.deepcopy(doc)
    a = _site(d, "four_chimneys")["pokemon"]["anchor"]
    a[1] += 1
    _refused(d, g, "the heightmap puts the anchor")


def test_a_trigger_outside_its_leash_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    pk = _site(d, "stallion_kraal")["pokemon"]
    pk["trigger"] = pk["leash"]
    p = tmp_path / "far_south.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit):
        FS.load(p)


def test_a_cache_without_an_items_hook_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    del _site(d, "garden_folly")["caches"][0]["items_hook"]
    p = tmp_path / "far_south.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit):
        FS.load(p)


def test_an_npc_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    _site(d, "garden_folly")["npc"] = {"name": "a gardener", "at": [0, 0, "the folly"]}
    p = tmp_path / "far_south.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit):
        FS.load(p)


# ------------------------------------------------------------------ the measurement the sites rest on


def test_the_density_measure_counts_each_far_south_site_once_in_its_own_cell(doc, g):
    import south_density as SD
    pts = SD.counted()
    ours = [(x, z) for lst in pts.values() for x, z, src in lst if src == "far_south.json"]
    assert sorted(ours) == sorted((float(r["site"]["centre"][0]), float(r["site"]["centre"][1])) for r in doc["residents"])
    # a residents-format file's relative offsets (a piece's `at`) are not places near the map's origin
    assert not [p for lst in pts.values() for p in lst if p[0] < SD.ORIGIN_GUARD and p[1] < SD.ORIGIN_GUARD]


def test_the_density_measure_still_finds_the_south_thinner_than_the_north(g):
    import south_density as SD
    b = SD.bands(SD.measure(g)["cells"])
    assert b["south F-H"]["per_land_km2"] < b["north A-E"]["per_land_km2"]
