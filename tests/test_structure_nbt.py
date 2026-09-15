"""tools/structure_nbt.py (template writer, Builder, load, capture) and tools/nbt.py region_chunks(wanted=...).

Structure templates are written with explicit tag types and read back through tools/nbt.py; capture reads a
synthetic region file built with the helpers in tests/test_reexport_tools.py.

Not covered: whether Minecraft 1.21.1 or WorldPainter 2.27.1 load these templates (DataVersion, palette property
strings, entity list), and capture against a real server save after `save-all flush`. Those need a WorldPainter
import or an in-game /place template, recorded as an experiment.
"""
import gzip
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import nbt  # noqa: E402
import structure_nbt as S  # noqa: E402
from test_reexport_tools import _section, _typed_chunk, _write_typed_region  # noqa: E402

PALETTE = [("minecraft:spruce_log", {"axis": "y"}),
           ("minecraft:spruce_leaves", {"distance": "1", "persistent": "true", "waterlogged": "false"}),
           ("minecraft:stone", {})]
BLOCKS = [(0, 0, 0, 0), (0, 1, 0, 0), (1, 2, 0, 1), (2, 2, 3, 2)]


# Removing this lets the writer drop or retype a field (size, palette properties, block states), so a template
# reads back as a different object than the one generated.
def test_dumps_round_trips_through_load(tmp_path):
    p = tmp_path / "t.nbt"
    p.write_bytes(S.dumps([3, 3, 4], PALETTE, BLOCKS))
    t = S.load(p)
    assert t["size"] == [3, 3, 4]
    assert t["data_version"] == S.DATA_VERSION == 3955
    assert t["palette"] == [(n, dict(props)) for n, props in PALETTE]
    assert t["blocks"] == [tuple(b) for b in BLOCKS]
    _, raw = nbt.load(p)
    assert raw["entities"] == []


# Removing this lets gzip stamp the current time into every file, so regenerated objects change sha256 with no
# content change and the library's hashes churn.
def test_dumps_is_byte_stable_with_zero_gzip_mtime():
    a = S.dumps([3, 3, 4], PALETTE, BLOCKS)
    b = S.dumps([3, 3, 4], PALETTE, BLOCKS)
    assert a == b
    assert a[:2] == b"\x1f\x8b" and a[4:8] == b"\x00\x00\x00\x00", "gzip header mtime is 0"
    assert gzip.decompress(a)[:1] == b"\x0a", "root is a compound"


# Removing this lets leaves overwrite a trunk (setdefault) or a later write lose to an earlier one (set).
def test_builder_set_wins_and_setdefault_never_overwrites():
    b = S.Builder()
    b.set(0, 0, 0, "minecraft:oak_leaves")
    b.set(0, 0, 0, "minecraft:oak_log", {"axis": "y"})
    b.setdefault(0, 0, 0, "minecraft:oak_leaves")
    b.setdefault(1, 0, 0, "minecraft:oak_leaves")
    assert b.get(0, 0, 0) == "minecraft:oak_log"
    assert b.get(1, 0, 0) == "minecraft:oak_leaves"
    assert b.get(5, 5, 5) is None
    b.set(2.4, 0.0, -0.0, "minecraft:stone")       # float coordinates land on the integer block
    assert b.get(2, 0, 0) == "minecraft:stone"


# Removing this lets a template keep negative or offset coordinates, or report a shift that does not map builder
# coordinates to template coordinates, which is how every object's origin (and WorldPainter offset) is derived.
def test_builder_to_bytes_trims_to_min_corner_and_returns_shift(tmp_path):
    pts = {(-3, 5, 2): "minecraft:oak_log", (1, 7, -4): "minecraft:oak_leaves", (0, 6, 0): "minecraft:stone"}
    b = S.Builder()
    for (x, y, z), n in pts.items():
        b.set(x, y, z, n)
    data, shift = b.to_bytes()
    assert shift == [3, -5, 4]
    p = tmp_path / "t.nbt"
    p.write_bytes(data)
    t = S.load(p)
    assert t["size"] == [5, 3, 7]
    got = {(x, y, z): t["palette"][s][0] for x, y, z, s in t["blocks"]}
    assert got == {(x + shift[0], y + shift[1], z + shift[2]): n for (x, y, z), n in pts.items()}
    assert min(k[0] for k in got) == 0 and min(k[1] for k in got) == 0 and min(k[2] for k in got) == 0
    # insertion order does not change the bytes, so a generator that iterates differently still hashes the same
    b2 = S.Builder()
    for (x, y, z), n in reversed(list(pts.items())):
        b2.set(x, y, z, n)
    assert b2.to_bytes()[0] == data


# Removing this lets air be written as template blocks, which would carve holes in terrain and other objects.
def test_builder_does_not_write_air(tmp_path):
    b = S.Builder()
    b.set(0, 0, 0, "minecraft:oak_log")
    b.set(0, 1, 0, "minecraft:air")
    b.set(0, 2, 0, "minecraft:oak_leaves")
    p = tmp_path / "t.nbt"
    p.write_bytes(b.to_bytes()[0])
    t = S.load(p)
    assert sorted(t["palette"][s][0] for *_, s in t["blocks"]) == ["minecraft:oak_leaves", "minecraft:oak_log"]


# Removing this lets describe() report a trunk base above the lowest log layer.
def test_describe_reports_lowest_log_columns(tmp_path):
    t = {"size": [3, 3, 3], "palette": [("minecraft:oak_log", {}), ("minecraft:oak_leaves", {})],
         "blocks": [(1, 0, 1, 0), (2, 0, 1, 0), (1, 1, 1, 0), (0, 2, 0, 1)]}
    d = S.describe(t)
    assert d["trunk_base"] == [(1, 1), (2, 1)]
    assert d["materials"] == {"minecraft:oak_log": 3, "minecraft:oak_leaves": 1} and d["blocks"] == 4


# Removing this lets region_chunks decompress chunks nobody asked for, or skip the one that was asked for (index is
# x + z * 32 in the region header).
def test_region_chunks_wanted_filter_yields_only_requested(tmp_path):
    stone = np.ones((16, 16, 16), np.int64)
    sec = _typed_chunk(_section(4, stone, ["minecraft:air", "minecraft:stone"]))
    path = tmp_path / "r.0.0.mca"
    _write_typed_region(path, {(1, 2): sec, (2, 1): sec, (0, 0): sec})
    assert sorted((x, z) for x, z, _ in nbt.region_chunks(path)) == [(0, 0), (1, 2), (2, 1)]
    assert [(x, z) for x, z, _ in nbt.region_chunks(path, wanted={(1, 2)})] == [(1, 2)]
    assert list(nbt.region_chunks(path, wanted=set())) == []


# Removing this lets capture misplace blocks by a chunk, section or axis ([y, z, x] section order), or keep blocks
# outside the requested box, so harvested vanilla trees come out scrambled or with neighbours attached.
def test_capture_reads_world_coordinates_inside_the_box(tmp_path):
    world = tmp_path / "world"
    grid = np.zeros((16, 16, 16), np.int64)
    grid[3, 5, 7] = 1          # section Y=4 (y 64..79) of chunk (1, 2): world (16 + 7, 64 + 3, 32 + 5)
    grid[3, 5, 15] = 2         # world (31, 67, 37): outside the box in x
    other = np.zeros((16, 16, 16), np.int64)
    other[0, 0, 0] = 1         # chunk (3, 2): world (48, 64, 32), not in any wanted chunk
    palette = ["minecraft:air", "minecraft:stone", "minecraft:dirt"]
    _write_typed_region(world / "region" / "r.0.0.mca", {
        (1, 2): _typed_chunk(_section(4, grid, palette)),
        (3, 2): _typed_chunk(_section(4, other, palette)),
    })
    b = S.capture(world, (20, 60, 30), (30, 70, 40))
    assert {k: v[0] for k, v in b.blocks.items()} == {(23, 67, 37): "minecraft:stone"}

