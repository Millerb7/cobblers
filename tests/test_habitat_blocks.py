"""Habitat Block manifest: static rules, presence in a stopped world, and the validator check.

Written in the same session as tools/habitat_blocks.py (not independently authored; see docs/HANDOVER_CODEX.md).
"""
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import habitat_blocks as HB  # noqa: E402
import validate_data as VD  # noqa: E402
from test_structure_inventory import _payload as _base_payload, _s  # noqa: E402

SPAWNS = {"habitats": [{"id": "great_crater_bowls"}, {"id": "route_1_ghost_mansion"}]}


class Longs(bytes):
    pass


def _payload(v):
    if isinstance(v, Longs):
        return 12, struct.pack(">i", len(v) // 8) + bytes(v)
    if isinstance(v, dict):
        out = b""
        for k, x in v.items():
            t, p = _payload(x)
            out += struct.pack(">b", t) + _s(k) + p
        return 10, out + b"\x00"
    if isinstance(v, list) and v and isinstance(v[0], dict):
        return 9, struct.pack(">bi", 10, len(v)) + b"".join(_payload(x)[1] for x in v)
    return _base_payload(v)


def write_region(path, chunks):
    header, body, sector = bytearray(8192), b"", 2
    for (lx, lz), comp in chunks.items():
        payload = zlib.compress(b"\x0a" + _s("") + _payload(comp)[1])
        blob = struct.pack(">IB", len(payload) + 1, 2) + payload
        blob += b"\x00" * (-len(blob) % 4096)
        idx = lx + lz * 32
        header[idx * 4:idx * 4 + 4] = struct.pack(">I", (sector << 8) | (len(blob) // 4096))
        body += blob
        sector += len(blob) // 4096
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + body)


def section_with(block_y, x, z, cancels):
    """A 16^3 section of air with one habitat block, packed at 4 bits per entry as the game stores it."""
    idx = np.zeros((16, 16, 16), dtype=np.uint64)
    idx[block_y & 15, z & 15, x & 15] = 1
    flat = idx.reshape(-1)
    longs = np.zeros(256, dtype=np.uint64)
    for i, v in enumerate(flat):
        longs[i // 16] |= np.uint64(int(v) << (4 * (i % 16)))
    return {"Y": block_y >> 4, "block_states": {
        "palette": [{"Name": "minecraft:air"},
                    {"Name": HB.BLOCK, "Properties": {"cancels_regular_spawns": cancels, "activated_style": "false"}}],
        "data": Longs(longs.astype(">u8").tobytes())}}


def block(bid="crater", x=1746, y=109, z=4815, r=24, pool="cobblers:great_crater_bowls", replace=True, status="placed"):
    return {"id": bid, "pool": pool, "style": "natural", "replace_spawns": replace, "range_of_influence": r,
            "position": {"x": x, "y": y, "z": z}, "status": status}


def world_with(tmp_path, entity, cancels="true", x=1746, y=109, z=4815):
    w = tmp_path / "world"
    cx, cz = x >> 4, z >> 4
    chunk = {"sections": [section_with(y, x, z, cancels)], "block_entities": [entity] if entity else []}
    write_region(w / "region" / ("r.%d.%d.mca" % (cx >> 5, cz >> 5)), {(cx & 31, cz & 31): chunk})
    (w / "level.dat").write_bytes(b"")
    return w


ENTITY = {"id": HB.BLOCK, "x": 1746, "y": 109, "z": 4815, "SpawningStyle": "cobblemon:natural",
          "PoolId": "cobblers:great_crater_bowls", "RangeOfInfluence": 24, "ReplaceSpawns": True}


# An unknown pool compiles to a block that places nothing the campaign authored.
def test_pool_must_be_a_compiled_habitat_pool():
    probs = HB.static_problems({"blocks": [block(pool="cobblers:nowhere")]}, SPAWNS)
    assert any("not a Habitat pool" in m for _, m in probs)


# EXP-021: two ReplaceSpawns ranges that overlap spawn nothing in the overlap.
def test_overlapping_replace_ranges_are_rejected_and_touching_ones_are_not():
    near = HB.static_problems({"blocks": [block("a"), block("b", x=1776, pool="cobblers:route_1_ghost_mansion")]}, SPAWNS)
    assert any("overlaps b" in m for _, m in near)
    apart = HB.static_problems({"blocks": [block("a"), block("b", x=1794, pool="cobblers:route_1_ghost_mansion")]}, SPAWNS)
    assert apart == []


# The function must reproduce the exact placement EXP-021 proved, or a re-export restores a different block.
def test_function_commands_are_the_proven_pair():
    cmds = HB.commands(block())
    assert cmds[0] == "setblock 1746 109 4815 cobblemon:habitat_block[cancels_regular_spawns=true,activated_style=false] replace"
    assert cmds[1] == ('data merge block 1746 109 4815 {SpawningStyle:"cobblemon:natural",ReplaceSpawns:1b,'
                       'RangeOfInfluence:24,PoolId:"cobblers:great_crater_bowls"}')


# A re-export erases in-game blocks; the world check is what notices.
def test_present_block_passes_and_absent_or_changed_block_fails(tmp_path):
    ok = world_with(tmp_path / "ok", ENTITY)
    assert HB.world_problems({"blocks": [block()]}, ok) == []
    gone = world_with(tmp_path / "gone", None)
    assert any("absent" in m for _, m in HB.world_problems({"blocks": [block()]}, gone))
    changed = world_with(tmp_path / "changed", dict(ENTITY, RangeOfInfluence=16), cancels="false")
    msgs = [m for _, m in HB.world_problems({"blocks": [block()]}, changed)]
    assert any("RangeOfInfluence" in m for m in msgs) and any("cancels_regular_spawns" in m for m in msgs)


# Planned blocks are not in the world yet and must not fail the presence check.
def test_planned_blocks_are_not_looked_for(tmp_path):
    empty = world_with(tmp_path, None)
    assert HB.world_problems({"blocks": [block(status="planned")]}, empty) == []


# The live world is never read (CLAUDE.md live-server gate).
def test_a_world_inside_the_server_runtime_is_refused(tmp_path):
    live = world_with(tmp_path / "cobblers-server", ENTITY)
    with pytest.raises(SystemExit):
        HB.world_problems({"blocks": [block()]}, live)


def _validate(tmp_path, blocks, world=None):
    d = tmp_path / "data"
    d.mkdir(parents=True)
    (d / "world.json").write_text(json.dumps({"schema": "cobblers.world/1"}))
    (d / "spawns.json").write_text(json.dumps(dict(SPAWNS, schema="cobblers.spawns/1", entries=[])))
    (d / "habitat_blocks.json").write_text(json.dumps({"schema": "cobblers.habitat-blocks/1", "blocks": blocks}))
    report = VD.Report()
    ctx = VD.Context(d, None, report, world)
    VD.check_schema(ctx)
    VD.check_habitat_blocks(ctx)
    return [(f.severity, f.message) for f in report.findings if f.check == "habitat-blocks"]


# Without a world, a placed block's presence is unknown: SKIPPED, never a pass.
def test_validator_skips_presence_without_a_world_and_fails_an_absent_block(tmp_path):
    assert [s for s, _ in _validate(tmp_path / "a", [block()])] == [VD.SKIPPED]
    gone = world_with(tmp_path / "w", None)
    got = _validate(tmp_path / "b", [block()], gone)
    assert any(s == VD.ERROR and "absent" in m for s, m in got)
