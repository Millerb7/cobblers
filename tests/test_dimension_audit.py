"""dimension_audit.py on a synthetic Nether: coverage, spill, and required structures."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dimension_audit as DA  # noqa: E402
from test_region_trim import write_region  # noqa: E402

BOUNDS = ["--min-x", "0", "--min-z", "0", "--max-x", "31", "--max-z", "15"]  # chunks (0,0) and (1,0)


@pytest.fixture()
def world(tmp_path):
    w = tmp_path / "world"
    blaine = {"Status": "minecraft:full", "structures": {"starts": {"cobbleverse:blaine": {"id": "cobbleverse:blaine"}}}}
    write_region(w / "DIM-1" / "region" / "r.0.0.mca", {
        (0, 0): blaine,
        (1, 0): {"Status": "minecraft:features"},
        (5, 5): {"Status": "minecraft:full"},              # outside the rectangle: spill
    })
    write_region(w / "DIM-1" / "region" / "r.-1.0.mca", {(3, 3): {"Status": "minecraft:full"}})
    catalog = {"structures": [
        {"id": "cobbleverse:blaine", "dimension": "nether", "cls": "PROGRESSION"},
        {"id": "cobbleverse:legendary/moltres", "dimension": "nether", "cls": "LEGENDARY"},
        {"id": "minecraft:fortress", "dimension": "nether", "cls": "NAMED"},
        {"id": "cobbleverse:brock", "dimension": "overworld", "cls": "PROGRESSION"},
    ]}
    (tmp_path / "structures.json").write_text(json.dumps(catalog), encoding="utf-8")
    return w


def run(world, tmp_path, *extra):
    out = tmp_path / "audit.json"
    code = DA.main(["--world", str(world), "--dimension", "the_nether", "--structures", str(tmp_path / "structures.json"),
                    "--out", str(out)] + BOUNDS + list(extra))
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_coverage_spill_and_starts(world, tmp_path):
    code, rep = run(world, tmp_path)
    assert code == 0
    assert rep["chunks_expected_inside"] == 2 and rep["chunks_saved_inside"] == 2
    assert rep["chunks_full_inside"] == 1 and rep["coverage_full"] == 0.5
    assert rep["status_inside"] == {"full": 1, "features": 1}
    assert rep["chunks_saved_outside"] == 2
    assert rep["starts"] == [{"structure": "cobbleverse:blaine", "x": 8, "z": 8}]


def test_catalog_check_only_uses_this_dimension(world, tmp_path):
    _, rep = run(world, tmp_path)
    cat = rep["catalog"]
    assert cat["by_class"]["PROGRESSION"] == {"present": ["cobbleverse:blaine"], "missing": []}
    assert cat["required_missing"] == ["cobbleverse:legendary/moltres"]
    assert "cobbleverse:brock" not in json.dumps(cat)


def test_fail_flags(world, tmp_path):
    assert run(world, tmp_path, "--fail-on-missing")[0] == 1
    assert run(world, tmp_path, "--fail-on-incomplete")[0] == 1
    assert run(world, tmp_path, "--require-classes", "PROGRESSION", "--fail-on-missing")[0] == 0
