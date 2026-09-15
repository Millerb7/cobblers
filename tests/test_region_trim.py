"""region_trim.py on synthetic region files: dry run changes nothing, apply backs up and trims."""
import json
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import region_trim as RT  # noqa: E402
from test_structure_inventory import nbt_bytes  # noqa: E402


def write_region(path, chunks):
    """chunks: {(local_x, local_z): compound}"""
    header = bytearray(8192)
    body = b""
    sector = 2
    for (lx, lz), comp in chunks.items():
        payload = zlib.compress(nbt_bytes(comp))
        blob = struct.pack(">IB", len(payload) + 1, 2) + payload
        blob += b"\x00" * (-len(blob) % 4096)
        idx = lx + lz * 32
        header[idx * 4:idx * 4 + 4] = struct.pack(">I", (sector << 8) | (len(blob) // 4096))
        body += blob
        sector += len(blob) // 4096
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + body)


@pytest.fixture()
def world(tmp_path):
    w = tmp_path / "world"
    start = {"Status": "minecraft:full", "structures": {"starts": {"cobbleverse:brock": {"id": "cobbleverse:brock"}}}}
    plain = {"Status": "full"}
    # r.0.0: chunk (0,0) inside, chunk (31,0) = blocks 496..511 outside a max_x of 479
    write_region(w / "region" / "r.0.0.mca", {(0, 0): plain, (31, 0): start})
    # r.-1.0 wholly outside min_x 0
    write_region(w / "region" / "r.-1.0.mca", {(5, 5): start})
    write_region(w / "entities" / "r.-1.0.mca", {(5, 5): plain})
    return w


BOUNDS = ["--min-x", "0", "--min-z", "0", "--max-x", "479", "--max-z", "479"]


def test_dry_run_reports_and_changes_nothing(world, tmp_path):
    before = {p: p.read_bytes() for p in world.rglob("*.mca")}
    out = tmp_path / "rep.json"
    assert RT.main(["--world", str(world)] + BOUNDS + ["--out", str(out)]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["chunks_inside"] == 1 and rep["chunks_outside"] == 2
    assert rep["starts_outside_by_id"] == {"cobbleverse:brock": 2}
    assert {(s["x"], s["z"]) for s in rep["starts_outside"]} == {(504, 8), (-424, 88)}
    assert {p: p.read_bytes() for p in world.rglob("*.mca")} == before


def test_apply_requires_a_backup_dir(world):
    with pytest.raises(SystemExit, match="backup"):
        RT.main(["--world", str(world)] + BOUNDS + ["--apply"])


def test_apply_backs_up_deletes_and_clears(world, tmp_path):
    backup = tmp_path / "backup"
    out = tmp_path / "rep.json"
    assert RT.main(["--world", str(world)] + BOUNDS + ["--apply", "--backup-dir", str(backup), "--out", str(out)]) == 0
    assert not (world / "region" / "r.-1.0.mca").exists()
    assert not (world / "entities" / "r.-1.0.mca").exists()
    assert (backup / "region" / "r.-1.0.mca").exists() and (backup / "entities" / "r.-1.0.mca").exists()
    assert (backup / "region" / "r.0.0.mca").exists()
    remaining = {(lx, lz) for lx, lz in RT.present_chunks(world / "region" / "r.0.0.mca")}
    assert remaining == {(0, 0)}
    again = tmp_path / "again.json"
    RT.main(["--world", str(world)] + BOUNDS + ["--out", str(again)])
    assert json.loads(again.read_text(encoding="utf-8"))["chunks_outside"] == 0


def test_backup_inside_the_world_is_refused(world):
    with pytest.raises(SystemExit, match="must not be inside"):
        RT.main(["--world", str(world)] + BOUNDS + ["--apply", "--backup-dir", str(world / "bk")])
