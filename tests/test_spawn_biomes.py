"""spawn_biomes.py against a miniature server directory built in the test.

The fake pack has a vanilla jar, a Cobblemon jar with a nested convention-tag
jar, and a datapack that overrides one spawn pool, so every expected count
below follows from the files written here.
"""
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import spawn_biomes as SB   # noqa: E402


def jar(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(name, content if isinstance(content, (bytes, str)) else json.dumps(content))
    return path


def pool(*spawns, **extra):
    return dict({"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [],
                 "spawns": list(spawns)}, **extra)


def spawn(sid, species, biomes, anti=None):
    s = {"id": sid, "pokemon": species, "type": "pokemon", "bucket": "common",
         "condition": {"biomes": biomes}}
    if anti:
        s["anticondition"] = {"biomes": anti}
    return s


BIOME = "data/minecraft/worldgen/biome/%s.json"
TAG = "data/%s/tags/worldgen/biome/%s.json"
POOL = "data/cobblemon/spawn_pool_world/%s.json"


@pytest.fixture()
def server(tmp_path):
    root = tmp_path / "server"
    jar(root / "versions" / "1.21.1" / "server-1.21.1.jar", {
        BIOME % "plains": {}, BIOME % "desert": {}, BIOME % "deep_dark": {}, BIOME % "nether_wastes": {},
        TAG % ("minecraft", "is_overworld"): {"values": ["minecraft:plains", "minecraft:desert", "minecraft:deep_dark"]},
        TAG % ("minecraft", "is_nether"): {"values": ["minecraft:nether_wastes"]},
    })
    conv = jar(tmp_path / "conv.jar", {TAG % ("c", "is_cave"): {"values": ["minecraft:deep_dark"]}})
    jar(root / "mods" / "Cobblemon.jar", {
        "fabric.mod.json": {"id": "cobblemon"},
        "META-INF/jars/conv.jar": conv.read_bytes(),
        TAG % ("cobblemon", "is_arid"): {"values": ["minecraft:desert", {"id": "terralith:dunes", "required": False}]},
        TAG % ("cobblemon", "is_sky"): {"values": [{"id": "terralith:skylands", "required": False}]},
        TAG % ("cobblemon", "is_cave"): {"values": [{"id": "#c:is_cave", "required": False}]},
        POOL % "0001_alpha": pool(spawn("alpha-1", "alpha", ["#cobblemon:is_arid"]),
                                  spawn("alpha-2", "alpha", ["minecraft:plains"], anti=["#cobblemon:is_arid"])),
        POOL % "0002_beta": pool(spawn("beta-1", "beta", ["#cobblemon:is_sky"])),
        POOL % "0003_gamma": pool(spawn("gamma-1", "gamma form=x", ["#cobblemon:is_cave"])),
        POOL % "0004_delta": pool(spawn("delta-1", "delta", ["minecraft:plains"]),
                                  neededInstalledMods=["notinstalled"]),
        POOL % "0005_eps": pool(spawn("eps-1", "eps", ["minecraft:nether_wastes"])),
    })
    jar(root / "datapacks" / "override.zip", {
        POOL % "0001_alpha": pool(spawn("alpha-1", "alpha", ["minecraft:desert"])),
    })
    jar(root / "datapacks" / "extra" / "ignored.zip", {
        POOL % "0006_zeta": pool(spawn("zeta-1", "zeta", ["minecraft:plains"])),
    })
    return root


PLAN = {
    "regions": [{"id": "meadow", "biomes": {"primary": "minecraft:plains",
                                            "bands": [{"biome": "minecraft:plains", "share": 1.0}]}},
                {"id": "rift", "biomes": {"deferred": True, "bands": [{"biome": "minecraft:desert", "share": 1.0}]}}],
    "tag_overlays": [{"tag": "#cobblemon:is_sky", "add_biomes": ["minecraft:plains"]}],
}


def refs(result):
    return {r["ref"]: r for r in result["references"]}


def test_default_scope_reads_only_the_cobblemon_jar(server):
    res = SB.analyse(SB.discover(server), "default", PLAN)
    assert res["skipped_pools"] == {"mod_requirements_unmet": 1}
    assert res["spawn_entries"] == 5            # alpha x2, beta, gamma, eps
    assert res["overworld_entries"] == 4        # eps is nether-only
    r = refs(res)
    assert r["#cobblemon:is_arid"]["members"] == ["minecraft:desert"]
    assert r["#cobblemon:is_arid"]["optional_unloaded"] == ["terralith:dunes"]
    assert r["#cobblemon:is_arid"]["anticondition_entries"] == 1
    # the nested convention-tag jar resolves the optional #c:is_cave
    assert r["#cobblemon:is_cave"]["members"] == ["minecraft:deep_dark"]
    assert r["minecraft:nether_wastes"]["dimension"] == "nether"
    assert r["#cobblemon:is_sky"]["dimension"] == "unresolved"


def test_coverage_counts_overlays_and_ignores_deferred_regions(server):
    res = SB.analyse(SB.discover(server), "default", PLAN)
    r = refs(res)
    assert r["minecraft:plains"]["covered"] is True
    assert r["#cobblemon:is_arid"]["covered"] is False, "desert only appears in a deferred region"
    assert r["#cobblemon:is_sky"]["covered"] is True
    assert r["#cobblemon:is_sky"]["via_overlay"] == ["minecraft:plains"]
    assert r["#cobblemon:is_cave"]["covered"] is False
    c = res["coverage"]
    assert c["overworld_species"] == 3                      # alpha, beta, gamma
    assert c["overworld_species_reachable"] == 2            # alpha via plains, beta via overlay
    assert c["unreachable_species"] == ["gamma"]


def test_pack_scope_applies_datapack_overrides_by_path(server):
    res = SB.analyse(SB.discover(server), "pack", PLAN)
    assert res["spawn_entries"] == 4            # alpha-2 was dropped by the override
    c = res["coverage"]
    assert "alpha" in c["unreachable_species"], "alpha now needs desert, which the plan defers"


def test_extra_datapacks_load_only_when_asked(server):
    assert "zeta" not in json.dumps(SB.analyse(SB.discover(server), "pack")["references"])
    with_extra = SB.analyse(SB.discover(server, include_extra=True), "pack")
    assert with_extra["spawn_entries"] == 5


def test_markdown_marks_gaps(server):
    md = SB.markdown(SB.analyse(SB.discover(server), "default", PLAN))
    assert "| `#cobblemon:is_cave` |" in md and "**GAP**" in md


@pytest.mark.parametrize("text,expected", [
    ("gamma form=x", "gamma"), ("pangoro held_item=cobblemon:fighting_gem", "pangoro"),
    ("Mr_Mime", "mr_mime"), ("  zubat	level=5", "zubat"),
])
def test_species_name_is_the_leading_id(text, expected):
    assert SB.species_name(text) == expected


def test_cli_requires_a_server_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("COBBLERS_SERVER_DIR", raising=False)
    with pytest.raises(SystemExit, match="server-dir"):
        SB.main(["--out", str(tmp_path / "x.json")])
