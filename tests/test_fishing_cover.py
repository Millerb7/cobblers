"""A rod catches only what we author, and every water has exactly the one table the guide shows (the owner, 2026-10-22).

The incident: on 2026-10-21 a friend fishing off Pallet's west shore hooked a Pyukumuku the fishing guide does not
list there. COBBLEVERSE-DP's own fishing details were live on water no authored list reached.

  - tools/suppress_inherited_spawns.py drops every inherited fishing detail (remove_fishing) and fails closed after
    writing if any is still live (verify_no_fishing, a raw text scan, not the generator's own walk)
  - tools/fishing_cover.py plans data/fishing_fill.json and tools/compile_spawns.py build_fishing applies it
  - tools/fishing_audit.py reads the COMPILED details back and checks water columns, the guide and the pack

The mutation tests change the GENERATOR (remove_fishing, is_fishing, apply, the fill file's reader), never the authored
data, and show the check then fails. Written by the implementing session at the brief's instruction, not by test-author:
an independent grade is still owed.

Not covered: what Cobblemon does on a cast (nothing here was cast in game); that Cobblemon honours "enabled": false for a
fishing-only file (proven for two other paths in EXP-012).
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fishing_audit as FA  # noqa: E402
import fishing_cover as FC  # noqa: E402
import suppress_inherited_spawns as SIS  # noqa: E402

POOL = "data/cobblemon/spawn_pool_world/"
MIXED = POOL + "0129_magikarp.json"
FISH_ONLY = POOL + "0349_feebas.json"
CONTEXT_KEY = POOL + "0771_pyukumuku.json"
HERD = POOL + "herds/0129_magikarp_herd.json"


def _d(i, mon, pos):
    return {"id": i, "pokemon": mon, "type": "pokemon", "spawnablePositionType": pos, "bucket": "common",
            "level": "5-20", "weight": 5.0, "condition": {"biomes": ["#cobblemon:is_ocean"]}}


def _server(tmp_path):
    server, world = tmp_path / "server", tmp_path / "world"
    (server / "mods").mkdir(parents=True)
    (server / "datapacks").mkdir()
    world.mkdir()
    with zipfile.ZipFile(server / "mods" / "cobblemon-additions-4.1.6.jar", "w") as z:
        z.writestr(HERD, json.dumps({"spawns": [{"id": "h1", "type": "pokemon-herd", "spawnablePositionType": "surface",
                                                 "bucket": "common", "weight": 5.0, "maxHerdSize": 3, "levelRange": "5-20",
                                                 "condition": {}, "herdablePokemon": [{"pokemon": "magikarp", "weight": 1.0}]}]}))
    with zipfile.ZipFile(server / "datapacks" / "COBBLEVERSE-DP-v31.zip", "w") as z:
        z.writestr(MIXED, json.dumps({"enabled": True, "spawns": [_d("magikarp-1", "magikarp", "seafloor"),
                                                                   _d("magikarp-2", "magikarp", "fishing"),
                                                                   _d("magikarp-3", "magikarp", "submerged")]}))
        z.writestr(FISH_ONLY, json.dumps({"enabled": True, "spawns": [_d("feebas-1", "feebas", "fishing")]}))
        # a detail keyed "context", the older notes' name for the position type: dropped as well
        z.writestr(CONTEXT_KEY, json.dumps({"enabled": True, "spawns": [
            {"id": "p1", "pokemon": "pyukumuku", "type": "pokemon", "context": "fishing", "bucket": "common",
             "level": "16-41", "weight": 2.0, "condition": {}}, _d("p2", "pyukumuku", "grounded")]}))
    sup = tmp_path / "spawn_suppression.json"
    sup.write_text(json.dumps({"removed_species": {"species": ["fluttermane"]}}), encoding="utf-8")
    return server, world, sup


def _run(tmp_path):
    server, world, sup = _server(tmp_path)
    out = tmp_path / "out"
    SIS.main(["--server", str(server), "--world", str(world), "--out", str(out), "--suppression", str(sup)])
    return out


def _doc(out, rel):
    return json.loads((out / rel).read_text(encoding="utf-8"))


def _enabled_fishing(out):
    """Independent of the tool: enabled files in the pack whose raw text carries a fishing position or context."""
    bad = []
    for f in out.rglob("*.json"):
        if f.name == "manifest.json":
            continue
        text = f.read_text(encoding="utf-8")
        if json.loads(text).get("enabled", True) is False:
            continue
        if '"spawnablePositionType":"fishing"' in text or '"context":"fishing"' in text:
            bad.append(f.name)
    return bad


# ------------------------------------------------------------------------------------------------ the inherited half


def test_every_inherited_fishing_detail_is_gone_and_the_rest_stay(tmp_path):
    # Without it Cobblemon's and Cobbleverse's own fishing stays live wherever no authored list reaches: the Pyukumuku.
    out = _run(tmp_path)
    mixed = _doc(out, MIXED)
    assert [s["id"] for s in mixed["spawns"]] == ["magikarp-1", "magikarp-3"], "the non-fishing details were lost or a fishing one kept"
    assert _doc(out, FISH_ONLY)["enabled"] is False, "a fishing-only inherited file is not disabled at its path"
    ctx = _doc(out, CONTEXT_KEY)
    assert [s["id"] for s in ctx["spawns"]] == ["p2"], "a detail keyed context=fishing was kept"
    assert {"dimensions": ["minecraft:the_nether"]} in mixed["spawns"][0]["anticonditions"], "the rest lost suppression"
    herd = _doc(out, HERD)["spawns"][0]
    assert herd["spawnablePositionType"] == "surface", "a non-fishing herd was touched"
    assert not _enabled_fishing(out)
    m = _doc(out, "manifest.json")
    assert m["fishing_details_removed"] == 3 and m["fishing_disabled_paths"] == 1


def test_a_generator_that_drops_no_fishing_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(SIS, "remove_fishing", lambda doc: 0)
    with pytest.raises(SystemExit, match="inherited fishing detail is still live"):
        _run(tmp_path)
    assert not (tmp_path / "out" / "pack.mcmeta").exists(), "a failed run left a pack that reads as generated"


def test_a_generator_that_misses_a_fishing_spelling_fails_closed(tmp_path, monkeypatch):
    # the verify is a raw text scan: a spelling the walk does not know still shows
    monkeypatch.setattr(SIS, "is_fishing", lambda d: d.get("spawnablePositionType") == "fishing")
    with pytest.raises(SystemExit, match="0771_pyukumuku"):
        _run(tmp_path)


def test_the_audit_flags_an_enabled_fishing_file_in_a_pack_and_not_a_disabled_one(tmp_path):
    pack = tmp_path / "pack" / "data" / "cobblemon" / "spawn_pool_world"
    pack.mkdir(parents=True)
    (pack / "a.json").write_text(json.dumps({"enabled": False, "spawns": [_d("x", "feebas", "fishing")]}), encoding="utf-8")
    problems, notes = [], []
    FA.check_inherited(tmp_path / "pack", None, None, problems, notes)
    assert problems == []
    (pack / "b.json").write_text(json.dumps({"spawns": [_d("y", "feebas", "fishing")]}), encoding="utf-8")
    FA.check_inherited(tmp_path / "pack", None, None, problems, notes)
    assert problems and "still hold a fishing detail" in problems[0]


# ------------------------------------------------------------------------------------------------ the authored half


def _heightmap():
    try:
        import ground as G
        return G.load()
    except Exception as e:  # noqa: BLE001
        pytest.skip("NOT_EXECUTED: no canonical heightmap here (%s)" % (str(e) or type(e).__name__)[:80])


@pytest.fixture(scope="module")
def ground():
    return _heightmap()


@pytest.fixture(scope="module")
def audit_result(ground):
    boxes, species = FA.compiled_details()
    problems, notes = [], []
    cnt, wet, lakes, rivers = FA.check_columns(boxes, problems, notes)
    FA.check_guide(boxes, species, cnt, wet, lakes, rivers, problems, notes)
    return problems, notes


def test_every_water_column_has_exactly_one_table_and_the_guide_shows_it(audit_result):
    problems, notes = audit_result
    assert problems == [], problems
    assert "sea columns" in notes[0], "the audit sampled no water: it proves nothing"


def test_the_audit_samples_a_lot_of_every_kind_of_water(audit_result):
    # a fixture that is nonempty: sea, lakes and river stations all contribute
    _, notes = audit_result
    import re
    n_sea, n_lake, n_river = (int(v) for v in re.findall(r"(\d+) (?:sea columns|lake points|river stations)", notes[0]))
    assert n_sea > 1_000_000 and n_lake > 1_000 and n_river > 100


def test_the_fill_file_is_what_plan_writes_today(ground):
    # Stale after a change to regions, spawns' fishing areas, marine zones, routes or the heightmap otherwise.
    assert json.loads(json.dumps(FC.plan(ground))) == FC.load()


def test_the_pallet_west_shore_water_had_no_table_and_now_has_a_sea_band(ground):
    # The 2026-10-21 Pyukumuku: sea off Pallet, in no sub-region raster and no band. (1060, 5360) is inside the first fill
    # box that lies x1024-1087, z5312-5375 on the heightmap's coast.
    import numpy as np
    x, z = 1060, 5360
    assert ground(x, z) < 62, "the probe column is not sea any more: pick another"
    before, _ = FA.compiled_details(fill=None)
    after, _ = FA.compiled_details()
    ix, iz = (x - FA.WORLD_MIN) // FA.STRIDE, (z - FA.WORLD_MIN) // FA.STRIDE
    assert FA.owner_raster(before)[iz, ix] == 0, "this column already had a table before the cover"
    assert FA.owner_raster(after)[iz, ix] == 1
    idx, names = FA.owner_index(after)
    assert names[int(idx[iz, ix])] == "sunset_shallows"


def test_the_audit_catches_a_generator_that_applies_no_cover(ground, monkeypatch):
    # Mutation of the GENERATOR (the fill's apply), authored data untouched: water is left without a table.
    # The compile's own guard (verify_exclusive) is switched off too, so this tests the audit and not the guard.
    monkeypatch.setattr(FC, "apply", lambda area_boxes, doc: area_boxes)
    monkeypatch.setattr(FC, "verify_exclusive", lambda area_boxes, zones: None)
    boxes, _ = FA.compiled_details()
    problems, notes = [], []
    FA.check_columns(boxes, problems, notes)
    import re
    none, several = (int(v) for v in re.findall(r"(\d+) with (?:none|several)", problems[0]))
    assert none > 10_000 and several > 1_000, problems


def test_the_audit_catches_a_cover_that_cedes_nothing(ground, monkeypatch):
    # apply that adds the fill and cuts nothing: cells two tables hold are caught by the compile and by the audit
    real = FC.apply

    def no_cut(area_boxes, doc):
        return real(area_boxes, dict(doc, cede={}))
    monkeypatch.setattr(FC, "apply", no_cut)
    with pytest.raises(SystemExit, match="not exclusive"):
        FA.compiled_details()


def test_a_stale_fill_file_fails_closed():
    base = {"a": [(-1024, -993, -1024, -993)]}
    with pytest.raises(SystemExit, match="cedes cells"):
        FC.apply(base, {"cede": {"a": [[0, 31, 0, 31]]}, "fill": {}})
    with pytest.raises(SystemExit, match="already holds"):
        FC.apply(base, {"cede": {}, "fill": {"a": [[-1024, -993, -1024, -993]]}})
    with pytest.raises(SystemExit, match="no fishing list"):
        FC.apply(base, {"cede": {}, "fill": {"gone": [[0, 31, 0, 31]]}})


def test_the_cover_never_reaches_a_spawn_free_zone():
    zone = [(-1024, -1000, -1024, -1000)]
    with pytest.raises(SystemExit, match="spawn-free"):
        FC.verify_exclusive({"a": [(-1024, -993, -1024, -993)]}, zone)


def test_the_guide_page_is_current():
    import player_guide_fishing as PG
    assert PG.main(["--check"]) == 0, "docs/player/fishing.html is stale: python tools/player_guide_fishing.py"
