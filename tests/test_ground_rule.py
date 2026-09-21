"""Placement tools take their ground from the heightmap or the plan, never from a world save.

Removing this lets the class of bug back in that has happened twice: the Displaced City cavern plan was
regenerated from a world the previous carve had damaged and followed the damage, and on 2026-09-20
tools/place_town.py seated Brock's houses on ground read from a world that already held the town, so
they climbed six to ten blocks above their own street. A world holds whatever was built into it last;
reading it to decide where to build reads your own output as the ground.

Reading a world to CHECK a result is allowed and necessary, and lives in the verify and audit tools
listed in VERIFY_ONLY.

Written by the same session that wrote tools/ground.py and converted the tools; not independently
reviewed (docs/HANDOVER_CODEX.md).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

# tools that decide where something goes in the world
PLACEMENT_TOOLS = [
    "place_town.py", "traders.py", "place_donor.py", "town_plan.py", "cavern_plan.py",
    "elder_trees.py", "maze_forest.py", "tree_grove.py", "world_tree.py", "habitat_blocks.py",
    "compile_spawns.py", "subregion_boxes.py", "waterways.py", "size_outliers.py",
]
# world_heights exists only to read a world. structure_nbt also WRITES structure files (Builder, dumps),
# which is harmless, so for it only the read, capture(), counts.
WORLD_MODULES = {"world_heights"}
WORLD_CALLS = {"extract", "capture"}
# functions inside a placement tool that read a world only to check what was built
VERIFY_ONLY = {
    "place_donor.py": {"read_world", "verify"},
    "habitat_blocks.py": {"read_world", "world_problems"},
}


def _world_reads(tree):
    """[(enclosing function or '<module>', line, what)] for every world read."""
    out = []

    def visit(node, owner):
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else owner
            if isinstance(child, ast.Import):
                for a in child.names:
                    if a.name.split(".")[0] in WORLD_MODULES:
                        out.append((owner, child.lineno, "import %s" % a.name))
            elif isinstance(child, ast.ImportFrom) and (child.module or "").split(".")[0] in WORLD_MODULES:
                out.append((owner, child.lineno, "from %s import" % child.module))
            elif (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                  and child.func.attr in WORLD_CALLS and isinstance(child.func.value, ast.Name)):
                out.append((owner, child.lineno, "%s.%s()" % (child.func.value.id, child.func.attr)))
            visit(child, name)

    visit(tree, "<module>")
    return out


def test_no_placement_tool_reads_ground_from_a_world():
    offenders = []
    for name in PLACEMENT_TOOLS:
        path = TOOLS / name
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        allowed = VERIFY_ONLY.get(name, set())
        for owner, line, what in _world_reads(tree):
            if owner not in allowed:
                offenders.append("%s:%d %s in %s" % (name, line, what, owner))
    assert not offenders, (
        "placement tools must take ground from tools/ground.py or the plan, never a world save:\n  "
        + "\n  ".join(offenders))


def test_no_placement_tool_accepts_a_world_as_ground():
    """--surface-world is kept only as a hidden flag that refuses to run, with the reason."""
    for name in PLACEMENT_TOOLS:
        path = TOOLS / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if '"--surface-world"' not in text:
            continue
        assert "argparse.SUPPRESS" in text, "%s still advertises --surface-world" % name
        assert re.search(r"if a\.surface_world:\s*\n(\s*#[^\n]*\n)*\s*raise SystemExit", text), \
            "%s accepts --surface-world without refusing it" % name


def test_the_detector_catches_the_two_incidents():
    """The rule is only worth having if it fires: both historical shapes are caught, a verify read is not."""
    place_town_before = (
        "import world_heights\n"
        "def main():\n"
        "    ground, _, meta = world_heights.extract(a.surface_world, box)\n")
    cavern_before = (
        "def main():\n"
        "    import world_heights\n"
        "    g, _, _ = world_heights.extract(a.surface_world, box)\n")
    audit_ok = (
        "import structure_nbt as SN\n"
        "def read_world(world, lo, hi):\n"
        "    return SN.capture(world, lo, hi)\n")
    assert any(w[0] == "<module>" for w in _world_reads(ast.parse(place_town_before)))
    assert any(w[0] == "main" for w in _world_reads(ast.parse(cavern_before)))
    assert [w for w in _world_reads(ast.parse(audit_ok)) if w[0] != "read_world"] == []


def test_ground_is_rounded_not_floored():
    """floor(h) is a block low across 48% of the map against a fresh export; round(h) matches 99.85%."""
    text = (TOOLS / "ground.py").read_text(encoding="utf-8")
    assert "np.round(" in text and "np.floor(" not in text
    for name in ("town_plan.py", "cavern_plan.py"):
        body = (TOOLS / name).read_text(encoding="utf-8")
        assert "math.floor(float(heights" not in body, "%s still floors the heightmap for ground" % name
