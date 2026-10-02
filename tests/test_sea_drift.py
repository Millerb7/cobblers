"""The Seaward Drift (tools/sea_drift.py) against its independent audit (tools/sea_drift_audit.py).

The audit replays the generated pack over a world made from the heightmap alone and checks rules the data states.
Clean on the pack as built is necessary and proves little on its own, so every other test here MUTATES THE GENERATOR
(CLAUDE.md, "How to prove an audit is independent"): data/sea_drift.json is left untouched, one function of the
generator is changed, the pack is rebuilt into a temporary folder, and the audit must catch it. A mutation of the data
would move the expectation with the output and prove nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sea_drift as SD            # noqa: E402
import sea_drift_audit as SA      # noqa: E402


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


def build(tmp_path, monkeypatch):
    out = tmp_path / "cobblers_sea_drift"
    monkeypatch.setattr(SD, "OUT", out)
    m = SD.model()
    SD.write(m)
    return m, out


def problems(out):
    return SA.audit(pack=out)["problems"]


def test_the_audit_is_clean_on_the_pack_as_built(ground, tmp_path, monkeypatch):
    m, out = build(tmp_path, monkeypatch)
    assert not m.problems
    res = SA.audit(pack=out)
    assert not res["problems"], res["problems"][:5]
    assert res["cover_min_measured"] >= res["cover_required"] == 4
    assert res["walk_nodes"] > 1000 and res["dark_floor_cells"] == 0 and res["leaks"] == 0


def test_the_records_in_the_shared_files_are_the_models(ground):
    """records --write was run after the last change to the model: a stale habitat block would sit in the wrong rock."""
    m = SD.model()
    habs, rew, pool = SD.records(m)
    hdoc = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))
    rdoc = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
    sdoc = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    assert [b for b in hdoc["blocks"] if b["id"].startswith(SD.HABITAT_PREFIX)] == habs
    assert [r for r in rdoc["rewards"] if r["id"].startswith(SD.REWARD_PREFIX)] == rew
    assert [h for h in sdoc["habitats"] if h["id"] == pool["habitat"]["id"]] == [pool["habitat"]]
    assert [e for e in sdoc["entries"] if e.get("scope") == pool["habitat"]["id"]] == pool["entries"]


def test_the_audit_catches_a_drift_built_with_too_little_cover(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "cover_blocks", lambda spec: 3)
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("water:") for p in problems(out))


def test_the_audit_catches_a_drift_with_no_lanterns(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "HANG", "minecraft:air")
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("light:") for p in problems(out))


def test_the_audit_catches_steps_without_stairs(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "stair", lambda block, facing: "minecraft:stone")
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("walk:") for p in problems(out))


def test_the_audit_catches_an_ore_that_is_a_spawn_condition(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(SD, "deep", lambda m, ore, y: "minecraft:coal_ore")
    _m, out = build(tmp_path, monkeypatch)
    ps = problems(out)
    assert any(p.startswith("blocks: minecraft:coal_ore is a spawn condition") for p in ps)
    assert any("is not an ore the data lists" in p for p in ps)


def test_the_audit_catches_a_shell_that_leaves_natural_ground_beside_the_drift(ground, tmp_path, monkeypatch):
    real = SD.shell_cells
    monkeypatch.setattr(SD, "shell_cells", lambda m: real(m) & ~SD.dilate(m.env, 1))
    _m, out = build(tmp_path, monkeypatch)
    assert any(p.startswith("sealed:") for p in problems(out))


def test_the_isles_pool_has_no_species_the_owner_is_tired_of():
    sdoc = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    pool = json.loads((ROOT / "data" / "sea_drift.json").read_text(encoding="utf-8"))["waters"]["pool"]
    species = {e["species"] for e in sdoc["entries"] if e.get("scope") == pool}
    assert species and not species & set(SA.NOT_WANTED)


def test_relic_islands_shape_is_unchanged_by_the_new_parameters():
    """tools/islet.py's island_top took radius, crown and grid parameters for the new isle; its defaults are Relic
    Island's and must give the same island they always did."""
    import numpy as np
    import islet as I
    a, ra = I.island_top(None, 62)
    b, rb = I.island_top(None, 62, seed=I.SEED, radius=I.RADIUS, top=I.TOP, half=I.RADIUS)
    assert np.array_equal(np.nan_to_num(a, nan=-1), np.nan_to_num(b, nan=-1)) and np.array_equal(ra, rb)
    assert a.shape == (2 * I.RADIUS + 1, 2 * I.RADIUS + 1)
    assert int(np.nanmax(a)) == 70 and int((~np.isnan(a)).sum()) == 2628
