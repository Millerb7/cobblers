"""The re-application's npc action clears plants at an NPC's feet and head, and nothing else.

Breaks without it: an NPC seated on painted foliage stands in a flower or a sweet berry bush (2026-10-11: three
Compact NPCs), which slows and hurts a player who walks up to talk, and npc_seats.py verify reports it as a solid block.
"""
import inspect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import reapply as R  # noqa: E402


def test_each_command_replaces_only_a_plant_tag_over_the_feet_and_head_column():
    cmds = R.stand_clear_commands(3647, 115, 6574)
    assert len(cmds) == 3
    pat = re.compile(r"^fill 3647 115 6574 3647 116 6574 minecraft:air replace (\S+)$")
    tags = [pat.match(c).group(1) for c in cmds]
    assert set(tags) == {"#minecraft:flowers", "#minecraft:saplings", "minecraft:sweet_berry_bush"}
    # never an unfiltered fill: one without `replace <filter>` would carve whatever the NPC stands in or under
    assert all(" replace " in c for c in cmds)


def test_the_npc_action_runs_the_clearing_before_it_looks_for_the_npc():
    src = inspect.getsource(R)
    i = src.index('elif kind == "npc":')
    block = src[i:src.index('elif kind == "props":', i)]
    clear, look, spawn = (block.index("stand_clear_commands(x, y, z)"), block.index("execute if entity"),
                          block.index("spawnnpcat"))
    assert clear < look < spawn
