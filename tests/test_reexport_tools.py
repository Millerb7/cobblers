"""level_dat.py, world_heights.py, reexport.wp_levels and the validator's terrain checks."""
import gzip
import json
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import level_dat as L  # noqa: E402
import world_heights as WH  # noqa: E402
import reexport as RX  # noqa: E402
import validate_data as V  # noqa: E402
import cell_stats as CS  # noqa: E402
import terrain as T  # noqa: E402
from test_region_trim import write_region  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "terrain"


# ---------------------------------------------------------------- level.dat

def _level(seed, extra=None):
    data = {
        "LevelName": (L.STRING, "w"),
        "Difficulty": (L.BYTE, 2),
        "BorderSize": (L.DOUBLE, 10240.0),
        "WorldGenSettings": (L.COMPOUND, {"seed": (L.LONG, seed), "generate_features": (L.BYTE, 1),
                                          "dimensions": (L.COMPOUND, {})}),
        "DataPacks": (L.COMPOUND, {"Enabled": (L.LIST, (L.STRING, ["vanilla"])),
                                   "Disabled": (L.LIST, (L.STRING, ["Terralith-DP.zip"]))}),
        "Empty": (L.LIST, (L.END, [])),
        "Longs": (L.LONG_ARRAY, [1, -2, 3]),
    }
    data.update(extra or {})
    return L.dumps("", {"Data": (L.COMPOUND, data)})


def test_level_dat_round_trip_keeps_types(tmp_path):
    raw = _level(-1234567890123456789)
    name, root = L.loads(raw)
    assert gzip.decompress(L.dumps(name, root)) == gzip.decompress(raw)
    assert L.data_of(root)["Difficulty"] == (L.BYTE, 2)


def test_seed_is_only_reported_as_a_digest(tmp_path):
    p = tmp_path / "level.dat"
    p.write_bytes(_level(987654321987654321))
    s = L.summary(p)
    assert "987654321987654321" not in json.dumps(s)
    assert s["seed_sha256"] == L.seed_digest(987654321987654321)


def test_carry_copies_keys_and_backs_up(tmp_path):
    old, new = tmp_path / "old.dat", tmp_path / "new.dat"
    old.write_bytes(_level(5, {"GameRules": (L.COMPOUND, {"doPokemonSpawning": (L.STRING, "true")})}))
    new.write_bytes(_level(5, {"DataPacks": (L.COMPOUND, {})}))
    copied, missing = L.carry(old, new, ["DataPacks", "GameRules", "Nope"])
    assert copied == ["DataPacks", "GameRules"] and missing == ["Nope"]
    d = L.data_of(L.load(new)[1])
    assert L.plain(d["DataPacks"])["Disabled"] == ["Terralith-DP.zip"]
    assert (tmp_path / "new.dat.carry-backup").exists()
    assert L.main(["seed-match", str(old), str(new)]) == 0


# ---------------------------------------------------------------- import line

def test_wp_levels_express_the_same_line():
    world = {"heightmap": {"bit_depth": 16},
             "import": {"low_in": 0.0, "high_in": 0.996078431, "low_out": 10.093458, "high_out": 200}}
    lv = RX.wp_levels(world)
    assert lv["world-low"] == 10 and lv["world-high"] == 200
    scale = (lv["world-high"] - lv["world-low"]) / (lv["image-high"] - lv["image-low"])
    for v, y in ((0, 10.093458), (10280, 40.0), (65278, 200.0)):
        assert abs((v - lv["image-low"]) * scale + lv["world-low"] - y) < 2e-3


# ---------------------------------------------------------------- world heights

def _pack(indices, bits):
    per = 64 // bits
    longs = []
    for i in range(0, len(indices), per):
        word = 0
        for j, v in enumerate(indices[i:i + per]):
            word |= int(v) << (j * bits)
        longs.append(word)
    return b"".join(struct.pack(">Q", w) for w in longs)


def _section(y, grid, palette):
    """grid: (16,16,16) palette indices [y,z,x]."""
    flat = grid.reshape(-1)
    bits = max(4, int(np.ceil(np.log2(len(palette))))) if len(palette) > 1 else 0
    bs = {"palette": [{"Name": n} for n in palette]}
    if bits:
        bs["data"] = _pack(flat, bits)
    return {"Y": y, "block_states": bs}


def test_chunk_columns_find_ground_and_water():
    palette = ["minecraft:air", "minecraft:stone", "minecraft:water", "minecraft:seagrass"]
    grid = np.zeros((16, 16, 16), np.int64)
    grid[:5] = 1                 # stone y 48..52 in section Y=3
    grid[5:14, :, 8:] = 2        # water to y61 on the east half
    grid[5, 0, 0] = 3            # seagrass on the west half does not count as ground
    chunk = {"Status": "full", "sections": [_section(3, grid, palette), _section(4, np.zeros((16, 16, 16), np.int64), ["minecraft:air"])]}
    ground, water, status = WH.chunk_columns(chunk)
    assert (ground == 52).all()
    assert (water[:, 8:] == 61).all() and (water[:, :8] == WH.NONE).all()
    assert status == "full"


def _typed_chunk(sec):
    """A plain section dict -> typed level_dat compound (long arrays as signed longs)."""
    bs = {"palette": (L.LIST, (L.COMPOUND, [{"Name": (L.STRING, p["Name"])} for p in sec["block_states"]["palette"]]))}
    raw = sec["block_states"].get("data")
    if raw:
        bs["data"] = (L.LONG_ARRAY, list(struct.unpack(">%dq" % (len(raw) // 8), raw)))
    section = {"Y": (L.BYTE, sec["Y"]), "block_states": (L.COMPOUND, bs)}
    return {"Status": (L.STRING, "full"), "sections": (L.LIST, (L.COMPOUND, [section]))}


def _write_typed_region(path, chunks):
    header = bytearray(8192)
    body = b""
    sector = 2
    for (lx, lz), comp in chunks.items():
        payload = L.dumps("", comp)                      # gzip, region compression type 1
        blob = struct.pack(">IB", len(payload) + 1, 1) + payload
        blob += b"\x00" * (-len(blob) % 4096)
        idx = lx + lz * 32
        header[idx * 4:idx * 4 + 4] = struct.pack(">I", (sector << 8) | (len(blob) // 4096))
        body += blob
        sector += len(blob) // 4096
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + body)


def test_extract_reads_regions_and_counts_outside(tmp_path):
    w = tmp_path / "world"
    stone = np.ones((16, 16, 16), np.int64)
    sec = _typed_chunk(_section(4, stone, ["minecraft:air", "minecraft:stone"]))   # ground y79
    _write_typed_region(w / "region" / "r.0.0.mca", {(0, 0): sec, (3, 0): sec})
    ground, water, meta = WH.extract(w, (0, 0, 31, 15), workers=1)
    assert meta["chunks_present"] == 2 - 1 and meta["chunks_saved_outside_bounds"] == 1
    assert ground.shape == (16, 32)
    assert (ground[:, :16] == 79).all() and (ground[:, 16:] == WH.NONE).all()


# ---------------------------------------------------------------- validator terrain checks

@pytest.fixture()
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    shutil.copy(FIXTURE / "world.json", d / "world.json")
    heights, world = T.load(FIXTURE / "world.json", str(FIXTURE))
    cells, _ = CS.measure(heights, world, 8, None)
    CS.write_cells(d / "cells.json", cells, world)
    return d


def _run(d):
    out = V.main(["--data", str(d), "--source-root", str(FIXTURE), "--json"])
    return out


def _findings(capsys):
    return json.loads(capsys.readouterr().out)


def test_cell_terrain_recomputes_and_passes(data_dir, capsys):
    assert _run(data_dir) == 0
    rep = _findings(capsys)
    msgs = [f for f in rep["findings"] if f["check"] in ("cell-terrain", "spatial")]
    assert not [f for f in msgs if f["severity"] == "SKIPPED"]
    assert any("no drift" in f["message"] for f in msgs)


def test_cell_terrain_fails_on_drift(data_dir, capsys):
    doc = json.loads((data_dir / "cells.json").read_text(encoding="utf-8"))
    doc["cells"][0]["terrain"]["mean_y"] += 5
    (data_dir / "cells.json").write_text(json.dumps(doc), encoding="utf-8")
    assert _run(data_dir) == 1
    assert any("drifted" in f["message"] for f in _findings(capsys)["findings"])


def test_spatial_flags_polygons_outside_bounds(data_dir, capsys):
    (data_dir / "regions.json").write_text(json.dumps({"geometry": {"polygon_tolerance_blocks": 0},
        "regions": [{"id": "r", "polygons": [[[0, 0], [300, 0], [0, 10]]]}]}), encoding="utf-8")
    assert _run(data_dir) == 1
    assert any("outside the landmass bounds" in f["message"] for f in _findings(capsys)["findings"])
