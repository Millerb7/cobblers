"""tools/rift_build.py: the Rift's wall, spires, gatehouses, cross-walls, floor light and biome.

Written in the same session as the builder. The generated-output tests skip when the Rift has not been generated in
this checkout (python tools/rift_build.py --source-root <root>); the helpers and verify's fail-closed rule do not.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits as FL  # noqa: E402
import rift_build as R  # noqa: E402

FDIR = ROOT / "build" / "datapacks" / "cobblers_rift" / "data" / "cobblers" / "function" / "rift"


def _plan():
    if not R.PLAN.is_file() or not FDIR.is_dir():
        pytest.skip("the Rift is not generated in this checkout (python tools/rift_build.py --source-root <root>)")
    return json.loads(R.PLAN.read_text(encoding="utf-8"))


def _functions():
    return {p.stem: p.read_text(encoding="utf-8").splitlines() for p in FDIR.glob("*.mcfunction")}


def test_ring_normals_point_out_of_the_polygon():
    # Without this the wall's second layer, the gatehouses' outside and the rubble scatter would face into the Rift.
    square = [[0, 0], [100, 0], [100, 100], [0, 100]]
    for (x, z), (nx, nz) in R.ring(square, [square]):
        assert not R.point_in(x + nx * 5, z + nz * 5, square)


def test_scan_rows_cover_the_polygon_and_nothing_else():
    square = [[10, 10], [20, 10], [20, 20], [10, 20]]
    rows = R.scan_rows([square], 0, 30)
    assert set(rows) == set(range(10, 20)) and all(s == [(10, 19)] for s in rows.values())


def test_verify_fails_without_a_plan(tmp_path, monkeypatch, capsys):
    # Fail closed: nothing planned is not "clean".
    monkeypatch.setattr(R, "PLAN", tmp_path / "none.json")
    assert R.verify(tmp_path) == 1
    assert "FAIL" in capsys.readouterr().out


def test_verify_fails_on_a_plan_missing_a_kind_it_builds(tmp_path, monkeypatch, capsys):
    # A plan that checks only the wall would call a Rift with no gatehouses clean.
    p = tmp_path / "plan.json"
    p.write_text(json.dumps({"checks": [[0, 64, 0, ["minecraft:obsidian"], "wall top"]]}), encoding="utf-8")
    monkeypatch.setattr(R, "PLAN", p)
    assert R.verify(tmp_path) == 1
    assert "not everything" in capsys.readouterr().out


def test_every_guard_site_has_a_barrier_directly_behind_the_guard_and_a_roofed_walkway():
    # RIFT_ZONES section 6: the NPC has no solid collision box, so a barrier behind it is what blocks, and the roof
    # stops anyone jumping it. Four guards, each with both.
    p = _plan()
    for g in ("G1", "G2", "G3", "G4"):
        kinds = [c[4] for c in p["checks"] if c[4].startswith(g + " ")]
        assert kinds.count("%s barrier" % g) == 2, g
        assert any(k == "%s roof over the walkway" % g for k in kinds), g
    assert p["counts"]["gatehouses"] == 4


def test_the_wall_is_never_low_enough_to_walk_over():
    # The rubble near a guard site is at least 4 high and never gapped, so the walkway stays the only way in on foot.
    spec = json.loads((ROOT / "data" / "rift.json").read_text(encoding="utf-8"))
    assert spec["rubble"]["height"][0] >= 4 and "gap_one_in" not in spec["rubble"]
    assert spec["wall"]["height_above_ground"] >= 4


def test_no_spire_stands_near_a_guard_site():
    p = _plan()
    near = json.loads((ROOT / "data" / "rift.json").read_text(encoding="utf-8"))["rubble"]["no_spires_within"]
    feet = [c for c in p["checks"] if c[4] == "spire foot"]
    assert feet
    for x, _, z, _, _ in feet:
        for (sx, sz), _ in p["sites"].values():
            assert (x - sx) ** 2 + (z - sz) ** 2 >= near ** 2


def test_every_function_passes_the_command_limits():
    # A refused or silently dropped command is a missing piece of wall nobody sees.
    _plan()
    for name, lines in _functions().items():
        assert FL.check_lines(lines, name) == [], name


def test_nothing_placed_decides_a_spawn():
    # Every block goes through the spawn-block policy: none of the Rift's blocks is named by a spawn condition.
    _plan()
    policy = (ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8")
    blocks = set()
    for lines in _functions().values():
        for l in lines:
            p = l.split()
            if p and p[0] in ("fill", "setblock"):
                blocks.add(p[-1])
    assert blocks and not [b for b in blocks if '"%s"' % b in policy]


def test_the_biome_is_painted_only_with_its_own_id_and_its_registry_entry_exists():
    _plan()
    spec = json.loads((ROOT / "data" / "rift.json").read_text(encoding="utf-8"))
    ns, path = spec["biome"]["id"].split(":")
    entry = ROOT / "build" / "datapacks" / "cobblers_rift_biome" / "data" / ns / "worldgen" / "biome" / (path + ".json")
    b = json.loads(entry.read_text(encoding="utf-8"))
    assert {"has_precipitation", "temperature", "downfall", "effects", "spawners", "spawn_costs", "carvers",
            "features"} <= set(b)
    ids = {l.split()[-1] for lines in _functions().values() for l in lines if l.startswith("fillbiome")}
    assert ids == {spec["biome"]["id"]}
