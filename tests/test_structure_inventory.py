"""nbt.py and structure_inventory.py against a miniature server and world built in the test."""
import gzip
import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nbt                      # noqa: E402
import structure_inventory as SI  # noqa: E402

# ---------------------------------------------------------------- tiny NBT writer (test only)


def _s(text):
    b = text.encode("utf-8")
    return struct.pack(">H", len(b)) + b


def _payload(v):
    if isinstance(v, bool):
        return 1, struct.pack(">b", int(v))
    if isinstance(v, int):
        return 3, struct.pack(">i", v)
    if isinstance(v, str):
        return 8, _s(v)
    if isinstance(v, dict):
        out = b""
        for k, x in v.items():
            t, p = _payload(x)
            out += struct.pack(">b", t) + _s(k) + p
        return 10, out + b"\x00"
    if isinstance(v, list):
        if not v:
            return 9, struct.pack(">bi", 0, 0)
        t = _payload(v[0])[0]
        return 9, struct.pack(">bi", t, len(v)) + b"".join(_payload(x)[1] for x in v)
    raise TypeError(v)


def nbt_bytes(root, name=""):
    return b"\x0a" + _s(name) + _payload(root)[1]


# ---------------------------------------------------------------- nbt.py


def test_nbt_reads_gzip_compound_with_lists():
    doc = {"size": [3, 4, 5], "palette": [{"Name": "minecraft:stone"}], "flag": True, "name": "x"}
    name, root = nbt.loads(gzip.compress(nbt_bytes(doc, "root")))
    assert name == "root"
    assert root["size"] == [3, 4, 5]
    assert root["palette"][0]["Name"] == "minecraft:stone"
    assert root["flag"] == 1 and root["name"] == "x"


def test_region_chunks_yields_each_stored_chunk(tmp_path):
    chunk = {"Status": "minecraft:full", "structures": {"starts": {"minecraft:igloo": {"id": "minecraft:igloo"}}}}
    body = zlib.compress(nbt_bytes(chunk))
    header = bytearray(8192)
    header[0:4] = struct.pack(">I", (2 << 8) | 1)         # chunk 0 at sector 2, 1 sector
    header[5 * 4:5 * 4 + 4] = struct.pack(">I", (3 << 8) | 1)  # chunk 5 at sector 3
    data = bytes(header)
    for _ in range(2):
        sector = struct.pack(">IB", len(body) + 1, 2) + body
        data += sector + b"\x00" * (4096 - len(sector))
    p = tmp_path / "r.0.0.mca"
    p.write_bytes(data)
    got = list(nbt.region_chunks(p))
    assert [(x, z) for x, z, _ in got] == [(0, 0), (5, 0)]
    assert got[0][2]["structures"]["starts"]["minecraft:igloo"]["id"] == "minecraft:igloo"


# ---------------------------------------------------------------- inventory


def jar(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            if isinstance(content, (dict, list)):
                content = json.dumps(content)
            z.writestr(name, content)
    return path


@pytest.fixture()
def server(tmp_path):
    root = tmp_path / "server"
    jar(root / "versions" / "1.21.1" / "server-1.21.1.jar", {
        "data/minecraft/worldgen/biome/plains.json": {}, "data/minecraft/worldgen/biome/crimson_forest.json": {},
        "data/minecraft/tags/worldgen/biome/is_overworld.json": {"values": ["minecraft:plains"]},
        "data/minecraft/tags/worldgen/biome/is_nether.json": {"values": ["minecraft:crimson_forest"]},
    })
    gym_nbt = gzip.compress(nbt_bytes({
        "size": [27, 17, 24],
        "palette": [{"Name": "rctmod:trainer_spawner"}, {"Name": "minecraft:chest"}, {"Name": "minecraft:command_block"},
                    {"Name": "lumymon:articuno_altar"}],
        "blocks": [
            {"pos": [1, 1, 1], "state": 0, "nbt": {"id": "rctmod:trainer_spawner", "TrainerIds": ["leader_x"]}},
            {"pos": [2, 1, 1], "state": 1, "nbt": {"id": "minecraft:chest", "LootTable": "demo:chests/gym"}},
            {"pos": [3, 1, 1], "state": 2, "nbt": {"id": "minecraft:command_block", "Command": "pokespawnat ~ ~ ~ mew"}},
            {"pos": [4, 1, 1], "state": 3},
        ],
        "entities": [],
    }))
    jar(root / "mods" / "demo.jar", {
        "fabric.mod.json": {"id": "cobblemon"},
        "data/demo/worldgen/structure/gym.json": {"type": "minecraft:jigsaw", "biomes": "plains", "start_pool": "demo:gym",
                                                  "size": 1, "max_distance_from_center": 80},
        "data/demo/worldgen/structure/hot_gym.json": {"type": "minecraft:jigsaw", "biomes": "#minecraft:is_nether",
                                                      "start_pool": "demo:gym", "size": 1},
        "data/demo/worldgen/structure_set/gyms.json": {"placement": {"type": "minecraft:random_spread", "spacing": 40, "separation": 20},
                                                       "structures": [{"structure": "demo:gym", "weight": 3},
                                                                      {"structure": "demo:hot_gym", "weight": 1}]},
        "data/demo/worldgen/template_pool/gym.json": {"elements": [{"element": {"element_type": "minecraft:single_pool_element",
                                                                                "location": "demo:gym"}}]},
        "data/demo/structure/gym.nbt": gym_nbt,
        "data/demo/tags/worldgen/structure/all_gyms.json": {"values": ["demo:gym"]},
        "data/cobblemon/spawn_pool_world/0001_a.json": {"spawns": [
            {"id": "a", "pokemon": "abra", "bucket": "common", "condition": {"structures": ["#demo:all_gyms"]}}]},
        "data/demo/loot_table/gym_map.json": {"pools": [{"entries": [{"functions": [{"function": "minecraft:exploration_map",
                                                                                       "destination": "#demo:all_gyms"}]}]}]},
        "data/demo/advancement/find_gym.json": {"criteria": {"x": {"trigger": "minecraft:location",
                                                                   "conditions": {"structures": "demo:gym"}}}},
    })
    return root


def test_inventory_reads_structures_templates_and_dependencies(server, tmp_path):
    out = tmp_path / "inv.json"
    md = tmp_path / "inv.md"
    assert SI.main(["--server-dir", str(server), "--out", str(out), "--markdown", str(md)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    recs = {r["id"]: r for r in d["structures"]}
    gym = recs["demo:gym"]
    # a namespace-less biome ID defaults to minecraft:
    assert gym["biomes_resolved"] == ["minecraft:plains"] and gym["dimension"] == "overworld"
    assert recs["demo:hot_gym"]["dimension"] == "nether"
    assert gym["structure_sets"][0]["spacing"] == 40 and gym["structure_sets"][0]["weight_share"] == 0.75
    assert gym["footprint"]["start_template_size_xyz"] == [27, 17, 24]
    c = gym["contents"]
    assert c["trainers"] == {"leader_x": 1}
    assert c["loot_tables"] == {"demo:chests/gym": 1}
    assert set(gym["signals"]) >= {"trainer", "loot", "command_blocks", "scripted_pokemon_spawn", "altar"}
    # the spawn names the structure through its tag
    assert gym["spawn_dependencies"]["entries"] == 1 and gym["spawn_dependencies"]["species"] == ["abra"]
    assert gym["advancements"] == ["demo:find_gym"]
    assert gym["referenced_by"]["loot_table"] == ["demo:gym_map"]
    assert "| `demo:gym` |" in md.read_text(encoding="utf-8")
    assert "`demo:hot_gym`" not in md.read_text(encoding="utf-8"), "overworld table only"


def test_world_scan_splits_starts_by_bounds(server, tmp_path):
    world = tmp_path / "world"
    (world / "region").mkdir(parents=True)
    (world / "level.dat").write_bytes(gzip.compress(nbt_bytes({"Data": {"BorderSize": 100, "WorldGenSettings": {
        "generate_features": True, "dimensions": {"minecraft:overworld": {"generator": {"type": "minecraft:noise",
                                                                                       "settings": "minecraft:overworld"}}}}}})))

    def region(path, chunk):
        body = zlib.compress(nbt_bytes(chunk))
        header = bytearray(8192)
        header[0:4] = struct.pack(">I", (2 << 8) | 1)
        sector = struct.pack(">IB", len(body) + 1, 2) + body
        path.write_bytes(bytes(header) + sector + b"\x00" * (4096 - len(sector)))

    region(world / "region" / "r.0.0.mca", {"Status": "full"})
    region(world / "region" / "r.-1.0.mca", {"Status": "minecraft:structure_starts",
                                             "structures": {"starts": {"demo:gym": {"id": "demo:gym"}}}})
    cfg = tmp_path / "world.json"
    cfg.write_text(json.dumps({"bounds": {"min_x": 0, "min_z": 0, "max_x": 8191, "max_z": 8191}}), encoding="utf-8")
    out = tmp_path / "inv.json"
    assert SI.main(["--server-dir", str(server), "--world", str(world), "--world-config", str(cfg), "--out", str(out)]) == 0
    ws = json.loads(out.read_text(encoding="utf-8"))["world_scan"]
    assert ws["starts_inside"] == {} and ws["starts_outside"] == {"demo:gym": 1}
    assert ws["chunk_status"]["inside"] == {"full": 1}
    assert ws["generate_features"] == 1 and ws["overworld_generator"] == "minecraft:noise"
