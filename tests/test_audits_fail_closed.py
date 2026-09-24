"""Audits fail closed: an audit that finds nothing to check FAILS, and expected counts come from plan data.

Codex review, 2026-09-21: tools/build_audit.py only reported a problem when it had placed something to compare, so a
missing or empty build passed. Each fixture here is an empty or absent build against a blank world; every one must
fail. They reproduce the defects and stay as tests.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_audit as BA  # noqa: E402


class BlankWorld:
    """Every block is air: the world a failed or skipped build leaves."""

    def block(self, x, y, z):
        return "minecraft:air"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "derived" / "sites").mkdir(parents=True)
    (tmp_path / "derived" / "cavern").mkdir(parents=True)
    (tmp_path / "build" / "datapacks").mkdir(parents=True)
    monkeypatch.setattr(BA, "ROOT", tmp_path)
    monkeypatch.setattr(BA, "BUILD", tmp_path / "build")
    monkeypatch.setattr(BA, "built_over", lambda *a, **k: set())
    return tmp_path


def test_forest_with_no_functions_fails(repo):
    (repo / "derived" / "sites" / "route1_forest.json").write_text(json.dumps({"objects_placed": 46052}))
    (repo / "build" / "datapacks" / "cobblers_route1" / "data" / "cobblers" / "function" / "route1").mkdir(parents=True)
    assert BA.forest(BlankWorld())["problems"]


def test_forest_with_no_plan_fails(repo):
    (repo / "build" / "datapacks" / "cobblers_route1" / "data" / "cobblers" / "function" / "route1").mkdir(parents=True)
    assert BA.forest(BlankWorld())["problems"]


def test_world_tree_with_no_functions_fails(repo):
    (repo / "derived" / "sites" / "world_tree_foothill_woods.json").write_text(json.dumps(
        {"centre": [0, 0], "trunk": [35, 35], "crown_radius": 78, "top_y": 535,
         "blocks": 100, "functions": ["00_tree", "90_foundation"]}))
    (repo / "build" / "datapacks" / "cobblers_worldtree" / "data" / "cobblers" / "function" / "worldtree").mkdir(parents=True)
    assert BA.world_tree(BlankWorld())["problems"]


def test_world_tree_with_one_matching_block_fails_the_canonical_plan_count(repo):
    names = ["00_tree", "01_tree", "02_tree", "03_tree", "90_foundation"]
    plan = {"centre": [0, 0], "trunk": [35, 35], "crown_radius": 78, "top_y": 10,
            "blocks": 1_264_724, "functions": names}
    (repo / "derived" / "sites" / "world_tree_foothill_woods.json").write_text(json.dumps(plan))
    fdir = repo / "build" / "datapacks" / "cobblers_worldtree" / "data" / "cobblers" / "function" / "worldtree"
    fdir.mkdir(parents=True)
    for name in names:
        body = "fill 0 10 0 0 10 0 minecraft:oak_leaves\n" if name == "00_tree" else ""
        (fdir / (name + ".mcfunction")).write_text(body)

    class OneBlockWorld(BlankWorld):
        def block(self, x, y, z):
            return "minecraft:oak_leaves" if (x, y, z) == (0, 10, 0) else "minecraft:air"

    problems = BA.world_tree(OneBlockWorld())["problems"]
    assert any("write 1 tree blocks, the plan expects 1264724" in p for p in problems)


def test_islet_with_an_empty_function_fails(repo):
    (repo / "derived" / "sites" / "relic_island.json").write_text(json.dumps(
        {"centre": [0, 0], "sea_level": 62, "radius": 10, "columns": 10, "columns_above_water": 5}))
    (repo / "build" / "islet").mkdir(parents=True)
    (repo / "build" / "islet" / "relic_island.mcfunction").write_text("")
    assert BA.islet(BlankWorld())["problems"]


def test_islet_with_one_matching_column_fails_the_canonical_plan_count(repo):
    (repo / "derived" / "sites" / "relic_island.json").write_text(json.dumps(
        {"centre": [0, 0], "sea_level": 62, "radius": 30, "columns": 2628, "columns_above_water": 1413}))
    (repo / "build" / "islet").mkdir(parents=True)
    (repo / "build" / "islet" / "relic_island.mcfunction").write_text(
        "fill 0 63 0 0 63 0 minecraft:dirt\n")

    class OneColumnWorld(BlankWorld):
        def block(self, x, y, z):
            return "minecraft:dirt" if (x, y, z) == (0, 63, 0) else "minecraft:air"

    problems = BA.islet(OneColumnWorld())["problems"]
    assert any("writes 1 columns, the plan expects 2628" in p for p in problems)
    assert any("raises 1 columns above sea, the plan expects 1413" in p for p in problems)


def _cavern_plan(repo, n=4, shell=True):
    (repo / "derived" / "cavern" / "plan.json").write_text(json.dumps({"cavern": [0, 0, n - 1, n - 1]}))
    arrs = {"floor": np.full((n, n), 30), "ceiling": np.full((n, n), 80), "top": np.full((n, n), 110)}
    if shell:
        arrs["shell_lo"] = np.full((n + 48, n + 48), 18)
        arrs["shell_hi"] = np.full((n + 48, n + 48), 100)
    np.savez(repo / "derived" / "cavern" / "plan.npz", **arrs)
    fn = repo / "build" / "datapacks" / "cobblers_cavern" / "data" / "cobblers" / "function" / "cavern"
    fn.mkdir(parents=True)
    (fn / "50_tunnel.mcfunction").write_text("")


def test_cavern_with_no_shell_data_fails(repo):
    _cavern_plan(repo, shell=False)
    probs = BA.cavern(BlankWorld())["problems"]
    assert any("no shell" in p for p in probs)


def test_cavern_whose_floor_the_town_rebuilds_entirely_fails(repo, monkeypatch):
    _cavern_plan(repo)
    monkeypatch.setattr(BA, "built_over", lambda *a, **k: {(x, z) for x in range(4) for z in range(4)})
    probs = BA.cavern(BlankWorld())["problems"]
    assert any("no column left to check the floor" in p for p in probs)


def test_audit_main_exits_non_zero_on_an_empty_build(repo, monkeypatch):
    (repo / "build" / "datapacks" / "cobblers_route1" / "data" / "cobblers" / "function" / "route1").mkdir(parents=True)
    monkeypatch.setattr(BA, "World", lambda *_: BlankWorld())
    assert BA.main(["--world", str(repo), "--only", "forest"]) == 1
