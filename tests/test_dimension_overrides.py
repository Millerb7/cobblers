"""tools/dimension_overrides.py: the Nether/End structure_set overrides and their independent audit.

The synthetic tests build a tiny upstream (a required zip, an optional extra/ zip) and check that the audit finds
every dangerous structure from the upstream files alone, and that a mutation of the GENERATOR (an override dropped,
a frequency changed) is caught while the data file is left untouched. The real-pack test runs the same audit on the
offline server snapshot when this machine has it.
"""
from __future__ import annotations

import copy
import gzip
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dimension_overrides as DO  # noqa: E402

SNAPSHOT = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05")


def _zip(path, members):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name, obj in members.items():
            if name.endswith(".nbt"):
                z.writestr(name, gzip.compress(obj))
            else:
                z.writestr(name, json.dumps(obj))


def _set(sid, spacing=25, sep=10, salt=1):
    return {"structures": [{"structure": sid, "weight": 1}],
            "placement": {"type": "minecraft:random_spread", "spacing": spacing, "separation": sep, "salt": salt}}


@pytest.fixture()
def upstream(tmp_path):
    root = tmp_path / "server"
    _zip(root / "datapacks" / "UP.zip", {
        "data/t/worldgen/structure/gym.json": {"biomes": ["minecraft:crimson_forest"], "start_pool": "t:gym"},
        "data/t/worldgen/structure_set/gym.json": _set("t:gym"),
        "data/t/structure/gym.nbt": b"...rctmod:trainer_spawner...",
        "data/t/worldgen/structure/alt.json": {"biomes": "#t:has_structure/alt", "start_pool": "t:alt"},
        "data/t/tags/worldgen/biome/has_structure/alt.json": {"values": ["minecraft:end_highlands"]},
        "data/t/worldgen/structure_set/alt.json": _set("t:alt", 120, 50, 2),
        "data/t/worldgen/structure/tower.json": {"biomes": "#minecraft:is_end", "start_pool": "t:tower"},
        "data/t/worldgen/template_pool/tower.json": {"elements": [{"element": {"location": "t:tower/top"}}]},
        "data/t/structure/tower/top.nbt": b"...minecraft:command_block...",
        "data/t/worldgen/structure_set/tower.json": _set("t:tower", 200, 125, 3),
        "data/t/worldgen/structure/benign.json": {"biomes": ["minecraft:nether_wastes"], "start_pool": "t:benign"},
        "data/t/worldgen/structure_set/benign.json": _set("t:benign"),
        "data/t/structure/benign.nbt": b"...nothing...",
        "data/t/worldgen/structure/ow.json": {"biomes": ["minecraft:plains"], "start_pool": "t:ow"},
        "data/t/worldgen/structure_set/ow.json": _set("t:ow"),
        "data/t/structure/ow.nbt": b"...rctmod:trainer_spawner...",
    })
    _zip(root / "datapacks" / "extra" / "OPT.zip", {
        "data/t/worldgen/structure/opt.json": {"biomes": ["minecraft:soul_sand_valley"], "start_pool": "t:opt"},
        "data/t/worldgen/structure_set/opt.json": _set("t:opt"),
        "data/t/structure/opt.nbt": b"...rctmod:trainer_spawner...",
    })
    data = {
        "suppress": [
            {"structure_set": "t:gym", "dimension": "the_nether", **_set("t:gym")},
            {"structure_set": "t:alt", "dimension": "the_end", **_set("t:alt", 120, 50, 2)},
            {"structure_set": "t:tower", "dimension": "the_end", **_set("t:tower", 200, 125, 3)},
        ],
        "kept": [],
        "not_covered": [{"structure_set": "t:opt", "structures": ["t:opt"], "dimension": "the_nether"}],
        "optional_packs": ["OPT.zip"],
    }
    legendaries = {"t:alt": "Testmon"}
    return [root / "datapacks"], data, legendaries, tmp_path / "pack"


def test_clean_synthetic_audit_finds_every_danger(upstream):
    roots, data, leg, pack = upstream
    DO.build(pack, data)
    problems, found = DO.audit(roots, pack, data, leg)
    assert problems == []
    assert set(found) == {"t:gym", "t:alt", "t:tower", "t:opt"}      # benign and overworld ones are not dangers


def test_generator_dropping_an_override_is_caught(upstream, monkeypatch):
    roots, data, leg, pack = upstream
    real = DO.files

    def drop_gym(d=None):
        out = real(d)
        out.pop("data/t/worldgen/structure_set/gym.json")
        return out
    monkeypatch.setattr(DO, "files", drop_gym)
    DO.build(pack, data)
    problems, _ = DO.audit(roots, pack, data, leg)
    assert any("t:gym" in p and "no override" in p for p in problems), problems


def test_generator_frequency_change_is_caught(upstream, monkeypatch):
    roots, data, leg, pack = upstream
    monkeypatch.setattr(DO, "FREQUENCY", 1.0)          # the audit's expectation must not follow the generator
    DO.build(pack, data)
    problems, _ = DO.audit(roots, pack, data, leg)
    assert sum("frequency 0.0" in p for p in problems) == 3, problems


def test_undeclared_danger_is_caught(upstream):
    roots, data, leg, pack = upstream
    d = copy.deepcopy(data)
    d["suppress"] = [e for e in d["suppress"] if e["structure_set"] != "t:tower"]
    DO.build(pack, d)
    problems, _ = DO.audit(roots, pack, d, leg)
    assert any(p.startswith("t:tower (set t:tower)") for p in problems), problems


def test_not_covered_must_be_optional(upstream):
    roots, data, leg, pack = upstream
    d = copy.deepcopy(data)
    d["suppress"] = [e for e in d["suppress"] if e["structure_set"] != "t:gym"]
    d["not_covered"].append({"structure_set": "t:gym", "structures": ["t:gym"], "dimension": "the_nether"})
    DO.build(pack, d)
    problems, _ = DO.audit(roots, pack, d, leg)
    assert any("t:gym: declared not covered" in p for p in problems), problems


def test_suppressing_an_optional_only_structure_is_refused(upstream):
    roots, data, leg, pack = upstream
    d = copy.deepcopy(data)
    d["not_covered"] = []
    d["suppress"].append({"structure_set": "t:opt", "dimension": "the_nether", **_set("t:opt")})
    DO.build(pack, d)
    problems, _ = DO.audit(roots, pack, d, leg)
    assert any("t:opt: suppressed, but no pack this world always loads" in p for p in problems), problems


def test_built_pack_matches_data():
    data = DO.load()
    out = DO.files(data)
    assert out["pack.mcmeta"]["pack"]["pack_format"] == 48
    assert len(out) == len(data["suppress"]) + 1
    for e in data["suppress"]:
        f = out[DO.set_path(e["structure_set"]).as_posix()]
        assert f["placement"]["frequency"] == 0.0
        assert f["structures"] == e["structures"]


def test_declarations_are_disjoint_and_the_owner_decisions_hold():
    data = DO.load()
    ids = [e["structure_set"] for k in ("suppress", "kept", "not_covered") for e in data[k]]
    assert len(ids) == len(set(ids))
    sup = {e["structure_set"] for e in data["suppress"]}
    # the owner's defect (2026-10-10): no second Blaine and no unearned Moltres
    assert {"cobbleverse:blaine", "cobbleverse:legendary/moltres"} <= sup
    # the Ruinous four stay Nether-generated (data/adopted_legendary_sites.json catalogue: stays_where_it_generates)
    assert "legendarymonuments:shrines" in {e["structure_set"] for e in data["kept"]}


def test_blaine_count_matches_the_hand_count():
    # window -1024..9215 = chunks -64..575; spacing 25, separation 10 -> 15 offsets per region. Regions -2..22 hold
    # all 15; region -3 (chunks -75..-61) holds 4 in the window, region 23 (575..) holds 1: 25 + 5/15 per axis
    p = {"spacing": 25, "separation": 10}
    assert DO.expected_candidates(p, -1024, 9215) == pytest.approx((25 + 5 / 15) ** 2)


def test_reapply_installs_it_world_local():
    import reapply as RA
    assert DO.PACK in RA.SERVER_PACKS and DO.PACK in RA.WORLD_LOCAL
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert 'add("dimension_overrides", "dimension_overrides.py", "build")' in src
    assert '"dimension_overrides.py", "audit"' in src


@pytest.mark.skipif(not (SNAPSHOT / "mods").is_dir(), reason="the offline server snapshot is local only")
def test_real_snapshot(tmp_path, monkeypatch):
    roots = [SNAPSHOT / "mods", SNAPSHOT / "datapacks"]
    DO.build(tmp_path / "pack")
    problems, found = DO.audit(roots, tmp_path / "pack")
    assert problems == []
    data = DO.load()
    declared = {s if isinstance(s, str) else s["structure"]
                for k in ("suppress", "kept", "not_covered") for e in data[k] for s in e["structures"]}
    assert set(found) == declared
    real = DO.files

    def drop_blaine(d=None):
        out = real(d)
        out.pop("data/cobbleverse/worldgen/structure_set/blaine.json")
        return out
    monkeypatch.setattr(DO, "files", drop_blaine)
    DO.build(tmp_path / "pack2")
    problems, _ = DO.audit(roots, tmp_path / "pack2")
    assert any("cobbleverse:blaine" in p for p in problems)
