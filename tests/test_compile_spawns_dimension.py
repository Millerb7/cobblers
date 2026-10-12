"""Every coordinate box the spawn compiler writes names its dimension.

Breaks without it: Cobblemon 1.8.0 reads an absent `dimensions` as every dimension
(docs/research/notes/spawn-dimension-condition-1.8.0.md), so an overworld box also spawns at the same x/z in the
Nether and in cobblers:pocket, the dungeons' dimension. On staging 2026-10-12 coast Pokemon spawned on the roof of a
nether-wastes dungeon shell.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import compile_spawns as C  # noqa: E402


def test_an_entry_with_no_dimension_is_written_as_overworld():
    for write in (C.box_condition, C.marine_condition):
        cond = write(0, 15, 0, 15, {"species": "wingull", "conditions": {}})
        assert cond["dimensions"] == ["minecraft:overworld"], write.__name__


def test_an_authored_dimension_list_is_kept_as_written():
    nether = {"species": "magmar", "conditions": {"dimensions": ["minecraft:the_nether"]}}
    assert C.box_condition(0, 15, 0, 15, nether)["dimensions"] == ["minecraft:the_nether"]
    # an empty list is an author's "every dimension": rare, deliberate, and not ours to rewrite
    anywhere = {"species": "ditto", "conditions": {"dimensions": []}}
    assert C.box_condition(0, 15, 0, 15, anywhere)["dimensions"] == []


def test_the_overworld_sky_rule_still_applies():
    cond = C.box_condition(0, 15, 0, 15, {"species": "pidgey", "conditions": {}})
    assert cond.get("canSeeSky") is True
