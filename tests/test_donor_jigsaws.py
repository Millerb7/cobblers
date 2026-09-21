"""A pack donor placed with `"jigsaws": "final_state"` has every jigsaw set to its own final state, rotated with the
building, and a record's removals still win. Without it a bca building's jigsaws stand in its floor as jigsaw blocks,
or, removed to air, leave holes (tools/place_donor.py jigsaw_commands)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import place_donor as PD  # noqa: E402

DOC = {"size": [4, 3, 4],
       "palette": [{"Name": "minecraft:jigsaw"}, {"Name": "minecraft:stone"}],
       "blocks": [{"pos": [1, 0, 2], "state": 0, "nbt": {"final_state": "minecraft:oak_planks"}},
                  {"pos": [3, 1, 0], "state": 0, "nbt": {"final_state": "minecraft:structure_void"}},
                  {"pos": [0, 0, 0], "state": 0, "nbt": {"final_state": "minecraft:dirt"}},
                  {"pos": [2, 0, 2], "state": 1}]}


def rec(**kw):
    r = {"id": "x", "position": {"x": 100, "y": 60, "z": 200}, "rotation": "none", "jigsaws": "final_state"}
    r.update(kw)
    return r


def test_each_jigsaw_takes_its_final_state():
    out = PD.jigsaw_commands(rec(), DOC)
    assert "setblock 101 60 202 minecraft:oak_planks" in out
    assert "setblock 103 61 200 minecraft:air" in out          # structure_void resolves to nothing
    assert "setblock 100 60 200 minecraft:dirt" in out
    assert len(out) == 3


def test_positions_turn_with_the_building():
    out = PD.jigsaw_commands(rec(rotation="clockwise_90"), DOC)
    # clockwise_90 sends template (x, z) to (-z, x) about the placement corner
    assert "setblock 98 60 201 minecraft:oak_planks" in out


def test_a_removal_beats_the_final_state():
    out = PD.jigsaw_commands(rec(remove_blocks=["minecraft:dirt"]), DOC)
    assert "setblock 100 60 200 minecraft:air" in out


def test_nothing_unless_asked():
    assert PD.jigsaw_commands(rec(jigsaws=None), DOC) == []
