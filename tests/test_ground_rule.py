"""No tool takes its ground from a world save: tools/ground_rule.py, by AST over every tool.

Removing this lets the class of bug back in that has happened twice: the Displaced City cavern plan was
regenerated from a world the previous carve had damaged and followed the damage, and on 2026-09-20
tools/place_town.py seated Brock's houses on ground read from a world that already held the town, so
they climbed six to ten blocks above their own street. A world holds whatever was built into it last;
reading it to decide where to build reads your own output as the ground.

Reading a world to CHECK a result is allowed and necessary: each tool declares the functions that do so in its own
WORLD_READS. Codex review, 2026-09-21: the detector this replaces scanned a hand-maintained list of 14 tools for two
call shapes, and missed a direct import-then-call and any read through a helper. The fixtures below are those misses
and stay as tests.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import ground_rule as GR  # noqa: E402

# stand-ins for the real readers, so each fixture is a whole small tool tree
NBT = "def region_chunks(path, wanted=None):\n    return open(path, 'rb')\n"
SNBT = ("import nbt\n"
        "def capture(world, lo, hi):\n"
        "    return list(nbt.region_chunks(world + '/region/r.0.0.mca'))\n")
BA = ("import nbt\n"
      "class World:\n"
      "    def __init__(self, d):\n"
      "        self.d = d\n"
      "    def block(self, x, y, z):\n"
      "        return nbt.region_chunks(self.d)\n")
WH = ("def _region_job(path):\n"
      "    return open(path + '/r.0.0.mca', 'rb')\n"
      "def extract(world, box):\n"
      "    from concurrent.futures import ProcessPoolExecutor\n"
      "    with ProcessPoolExecutor() as ex:\n"
      "        return list(ex.map(_region_job, [world]))\n")


def reads(tool_src, name="place_town", declared_ok=True):
    srcs = {"nbt": NBT + "WORLD_READS = {'region_chunks'}\n", "structure_nbt": SNBT + "WORLD_READS = {'capture'}\n",
            "build_audit": BA + "WORLD_READS = {'World'}\n", "world_heights": WH + "WORLD_READS = {'_region_job', 'extract'}\n",
            name: tool_src}
    res = GR.analyse(sources=srcs)
    return res.get(name, {"reads": set(), "declared": set()}), GR.problems(res)


def test_the_repository_obeys_the_rule():
    bad = GR.problems(GR.analyse())
    assert not bad, "\n".join(bad)


def test_it_covers_every_tool_not_a_list():
    # a tool added tomorrow is analysed without anybody remembering to add it
    names = {p.stem for p in TOOLS.glob("*.py")} - {"ground_rule"}
    import ast
    parsed = {n for n in names if ast.parse((TOOLS / (n + ".py")).read_text(encoding="utf-8"))}
    assert parsed == names and len(names) > 50


def test_the_two_incidents_are_caught():
    place_town_before = ("import world_heights\n"
                         "def build(a, box):\n"
                         "    ground, _, meta = world_heights.extract(a.surface_world, box)\n")
    cavern_before = ("def main():\n"
                     "    import world_heights\n"
                     "    g, _, _ = world_heights.extract(a.surface_world, box)\n")
    r, bad = reads(place_town_before)
    assert "build" in r["reads"] and bad
    r, bad = reads(cavern_before, name="cavern_plan")
    assert "main" in r["reads"] and bad


def test_a_direct_import_then_call_is_caught():
    # the shape the old detector missed: `from m import f` then `f(...)`
    r, bad = reads("from structure_nbt import capture\n"
                   "def seat(world):\n"
                   "    return capture(world, (0, 0, 0), (1, 1, 1))\n")
    assert r["reads"] == {"seat"} and bad


def test_a_read_through_a_helper_class_is_caught():
    r, bad = reads("import build_audit as B\n"
                   "def ground_at(world, x, z):\n"
                   "    w = B.World(world)\n"
                   "    return w.block(x, 64, z)\n")
    assert r["reads"] == {"ground_at"} and bad


def test_a_read_two_calls_deep_is_caught():
    r, bad = reads("from structure_nbt import capture as grab\n"
                   "def _helper(w):\n"
                   "    return grab(w, 0, 1)\n"
                   "def plan(w):\n"
                   "    return _helper(w)\n")
    assert r["reads"] == {"_helper", "plan"} and bad


def test_a_declared_check_passes_and_a_stale_declaration_fails():
    r, bad = reads("import build_audit\n"
                   "WORLD_READS = {'verify'}\n"
                   "def verify(world):\n"
                   "    return build_audit.World(world).block(0, 0, 0)\n")
    assert r["reads"] == {"verify"} and not bad
    r, bad = reads("WORLD_READS = {'verify'}\n"
                   "def verify(world):\n"
                   "    return 1\n")
    assert bad and "do not read a world" in bad[0]


def test_a_tool_that_reads_nothing_is_clean():
    r, bad = reads("import ground\n"
                   "def seat(g, x, z):\n"
                   "    return g(x, z)\n")
    assert r["reads"] == set() and not bad


def test_no_tool_accepts_a_world_as_ground():
    """--surface-world is kept only as a hidden flag that refuses to run, with the reason; any tool, not a list."""
    for path in sorted(TOOLS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if '"--surface-world"' not in text:
            continue
        assert "argparse.SUPPRESS" in text, "%s still advertises --surface-world" % path.name
        assert re.search(r"if a\.surface_world:\s*\n(\s*#[^\n]*\n)*\s*raise SystemExit", text), \
            "%s accepts --surface-world without refusing it" % path.name


def test_ground_is_rounded_not_floored():
    """floor(h) is a block low across 48% of the map against a fresh export; round(h) matches 99.85%."""
    text = (TOOLS / "ground.py").read_text(encoding="utf-8")
    assert "np.round(" in text and "np.floor(" not in text
    for name in ("town_plan.py", "cavern_plan.py"):
        body = (TOOLS / name).read_text(encoding="utf-8")
        assert "math.floor(float(heights" not in body, "%s still floors the heightmap for ground" % name
