"""The re-export builds are checked by their result: a function's own fills are replayed and compared with the world.

Without this, 13,586 of Route 1's 46,052 trees and 165 columns of the cavern's roof cap were missing from the
disposable world, lost to functions that wrote into chunks nobody had loaded, and nothing reported it
(2026-09-21). Offline: a fake world stands in for region files.

Written by the same session that wrote tools/build_audit.py; not independently reviewed (docs/HANDOVER_CODEX.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_audit as BA  # noqa: E402


class FakeWorld:
    def __init__(self, blocks):
        self.blocks = blocks

    def block(self, x, y, z):
        return self.blocks.get((x, y, z), "minecraft:air")


def test_replay_takes_the_last_write_and_honours_replace():
    lines = ["fill 0 0 0 2 3 0 minecraft:stone", "fill 0 3 0 2 3 0 minecraft:air", "setblock 1 1 0 minecraft:glass",
             "fill 0 0 0 2 0 0 minecraft:dirt replace minecraft:stone", "fill 0 2 0 2 2 0 minecraft:sand replace minecraft:gravel"]
    col = BA.replay(lines, [(1, 0)])[(1, 0)]
    assert col == {0: "minecraft:dirt", 1: "minecraft:glass", 2: "minecraft:stone", 3: "minecraft:air"}


def test_block_states_do_not_count_as_a_mismatch():
    exp = {(0, 0): {5: "minecraft:oak_leaves"}}
    n, ok, _ = BA.compare_columns(FakeWorld({(0, 5, 0): "minecraft:oak_leaves"}), exp)
    assert (n, ok) == (1, 1)


def test_a_missing_block_is_reported_with_where_and_what():
    n, ok, bad = BA.compare_columns(FakeWorld({}), {(3, 4): {7: "minecraft:stone"}})
    assert (n, ok) == (1, 0) and "(3, 7, 4) holds minecraft:air, the function wrote minecraft:stone" in bad[0]


def test_the_thresholds_are_fixed_and_strict():
    # set before any run: a roof with one hole in 40,000 columns fails
    assert BA.ROOF_OK == 1.0 and BA.FLOOR_OK >= 0.98 and BA.TRUNKS_OK >= 0.98 and BA.COLUMNS_OK >= 0.99
