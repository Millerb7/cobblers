"""No wild spawn, inherited or ours, names a paradox (the owner, 2026-10-08: "Paradoxes are dungeon content").

Inherited: tools/suppress_inherited_spawns.py drops every detail and herd member of a species
data/spawn_suppression.json removed_species lists, and disables (EXP-012 V4/V5: "enabled": false at the same path) a
file left with none. It fails closed twice: when the server's Cobblemon jar labels a paradox the list lacks, and after
writing, when any inherited path is still enabled and names a listed species (verify_removed_species, a raw-text scan
rather than the generator's own detail walk).

Ours: tools/validate_data.py check wild-paradox reads every species/pokemon value in data/spawns.json and the Mega dens'
lines.

The mutation tests change the GENERATOR (remove_species), never the fixture, and show the run then fails.

Independent source for the species list: the jar's own "paradox" label (the fixture jar below models the 1.8.0 jar's
data/cobblemon/species/generation9/<name>.json shape, labels ["gen9", "paradox"]), not the authored list.

Not covered, and it needs a running server: that Cobblemon honours "enabled": false for these 22 paths (proven for two
other paths in EXP-012) and /checkspawn in a spooky biome at night lists no Flutter Mane.
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import suppress_inherited_spawns as SIS  # noqa: E402
import validate_data as V  # noqa: E402

POOL = "data/cobblemon/spawn_pool_world/"
ONLY = POOL + "0987_fluttermane.json"
MIXED = POOL + "mixed.json"
HERD = POOL + "herds/mixed_herd.json"
HERD_ONLY = POOL + "herds/fluttermane_herd.json"


def _detail(i, mon):
    return {"id": i, "pokemon": mon, "type": "pokemon", "spawnablePositionType": "grounded", "bucket": "rare",
            "level": "45-60", "weight": 1.5, "condition": {"biomes": ["#cobblemon:is_spooky"]}}


def _herd(i, *mons):
    return {"id": i, "type": "pokemon-herd", "spawnablePositionType": "grounded", "bucket": "rare", "weight": 5.0,
            "maxHerdSize": 3, "levelRange": "5-20", "condition": {},
            "herdablePokemon": [{"pokemon": m, "weight": 1.0, "levelRange": "5-20"} for m in mons]}


def _server(tmp_path, labelled=("fluttermane", "ironhands")):
    server, world = tmp_path / "server", tmp_path / "world"
    (server / "mods").mkdir(parents=True)
    (server / "datapacks").mkdir()
    world.mkdir()
    with zipfile.ZipFile(server / "mods" / "Cobblemon-fabric-1.8.0+1.21.1.jar", "w") as z:
        for name in labelled:
            z.writestr("data/cobblemon/species/generation9/%s.json" % name,
                       json.dumps({"name": name.title(), "labels": ["gen9", "paradox"]}))
        z.writestr("data/cobblemon/species/generation2/misdreavus.json",
                   json.dumps({"name": "Misdreavus", "labels": ["gen2"]}))
        z.writestr(HERD, json.dumps({"spawns": [_herd("h1", "misdreavus", "fluttermane alpha=true")]}))
        z.writestr(HERD_ONLY, json.dumps({"spawns": [_herd("h2", "fluttermane")]}))
    with zipfile.ZipFile(server / "datapacks" / "COBBLEVERSE-DP-v31.zip", "w") as z:
        z.writestr(ONLY, json.dumps({"enabled": True, "spawns": [_detail("fluttermane-1", "fluttermane")]}))
        z.writestr(MIXED, json.dumps({"enabled": True, "spawns": [_detail("m1", "cobblemon:fluttermane"),
                                                                   _detail("m2", "misdreavus")]}))
    sup = tmp_path / "spawn_suppression.json"
    sup.write_text(json.dumps({"removed_species": {"species": ["fluttermane", "ironhands"]}}), encoding="utf-8")
    return server, world, sup


def _run(tmp_path, **kw):
    server, world, sup = _server(tmp_path, **kw)
    out = tmp_path / "out"
    SIS.main(["--server", str(server), "--world", str(world), "--out", str(out), "--suppression", str(sup)])
    return out


def _doc(out, rel):
    return json.loads((out / rel).read_text(encoding="utf-8"))


def _live_naming(out, species):
    """Independent of the tool: every enabled file in the pack whose raw text names a species as a pokemon value."""
    bad = []
    for f in out.rglob("*.json"):
        if f.name == "manifest.json":
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        if doc.get("enabled", True) is False:
            continue
        text = f.read_text(encoding="utf-8")
        bad += [f.name for s in species if '"pokemon":"%s' % s in text or '"pokemon":"cobblemon:%s' % s in text]
    return bad


def test_every_paradox_spawn_is_gone_and_the_rest_stay(tmp_path):
    out = _run(tmp_path)
    assert _doc(out, ONLY)["enabled"] is False, "a paradox-only inherited file is not disabled at its path"
    assert _doc(out, HERD_ONLY)["enabled"] is False
    mixed = _doc(out, MIXED)
    assert mixed.get("enabled", True) is not False
    assert [s["id"] for s in mixed["spawns"]] == ["m2"], "the mixed file lost its other species or kept the paradox"
    assert {"dimensions": ["minecraft:the_nether"]} in mixed["spawns"][0]["anticonditions"], "the rest lost suppression"
    herd = _doc(out, HERD)["spawns"][0]["herdablePokemon"]
    assert [h["pokemon"] for h in herd] == ["misdreavus"]
    assert not _live_naming(out, ["fluttermane", "ironhands"])
    manifest = _doc(out, "manifest.json")
    assert manifest["removed_species_details"] == 4 and len(manifest["disabled_paths"]) == 2


def test_a_jar_paradox_the_list_lacks_fails_closed(tmp_path):
    with pytest.raises(SystemExit, match="ironjugulis"):
        _run(tmp_path, labelled=("fluttermane", "ironhands", "ironjugulis"))


def test_a_generator_that_removes_nothing_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(SIS, "remove_species", lambda doc, removed: 0)
    with pytest.raises(SystemExit, match="still a live inherited spawn"):
        _run(tmp_path)
    assert not (tmp_path / "out" / "pack.mcmeta").exists(), "a failed run left a pack that reads as generated"


def test_a_generator_that_misses_herd_members_fails_closed(tmp_path, monkeypatch):
    def top_level_only(doc, removed):
        before = len(doc.get("spawns", []))
        doc["spawns"] = [s for s in doc.get("spawns", []) if SIS.species_token(s.get("pokemon")) not in removed]
        return before - len(doc["spawns"])
    monkeypatch.setattr(SIS, "remove_species", top_level_only)
    with pytest.raises(SystemExit, match="mixed_herd"):
        _run(tmp_path)


def test_the_authored_list_is_the_22():
    """The list is the jar's 20 paradox-labelled species plus Koraidon and Miraidon (docs/research/notes/
    paradox-pokemon-1.8.0.md section 1, read from the jar). The run against the real jar checks the 20 itself."""
    doc = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))
    species = doc["removed_species"]["species"]
    assert len(species) == len(set(species)) == 22
    assert {"fluttermane", "koraidon", "miraidon", "walkingwake", "ironleaves"} <= set(species)


def _check(tmp_path, spawns):
    (tmp_path / "spawn_suppression.json").write_text(
        (ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"), encoding="utf-8")
    ctx = V.Context(tmp_path, None, V.Report())
    ctx.files["spawns.json"] = SimpleNamespace(doc=spawns)
    V.check_wild_paradox(ctx)
    return [f.message for f in ctx.report.findings if f.severity == V.ERROR]


def test_our_spawn_data_names_no_paradox(tmp_path):
    spawns = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    assert _check(tmp_path, spawns) == []


@pytest.mark.parametrize("where", ["entry", "habitat", "nether"])
def test_a_paradox_in_our_spawn_data_is_caught(tmp_path, where):
    spawns = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    if where == "entry":
        spawns["entries"].append(dict(spawns["entries"][0], id="x.fluttermane", species="fluttermane"))
    elif where == "habitat":
        spawns["habitats"][0]["entries"].append({"species": "Flutter Mane", "pokemon": "fluttermane"})
    else:
        spawns["nether_tables"][0]["species"].append("ironmoth")
    errors = _check(tmp_path, spawns)
    assert errors and "removed_species" in errors[0], errors
