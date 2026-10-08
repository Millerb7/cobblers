"""tools/suppress_inherited_spawns.py: the suppression boxes are bound to the overworld (review N153).

Independent source: the Cobblemon 1.8.0 bytecode read on 2026-10-08 (docs/research/notes/
spawn-dimension-condition-1.8.0.md). SpawningCondition.fits returns false when "dimensions" is non-null, non-empty and
does not contain world.dimension().location(); coordinate bounds that are absent restrict nothing; SpawnDetail.isSatisfiedBy
drops a detail when ANY of its anticonditions is satisfied. `_anti_satisfied` below is that rule written from the note,
not from the tool, and the box under test is read from data/routes.json directly, not from the tool's merged set.

Before the fix the boxes were plain minX/maxX/minZ/maxZ, so every overworld route box also removed every inherited Nether
and End spawn at the same x/z. test_the_unbound_boxes_of_before_the_fix_are_caught mutates the GENERATOR (the
anticondition builder) back to that shape and shows the check fails on it.

Not covered, and it needs a running server: that Cobblemon loads the bound anticonditions and that an inherited Nether
spawn appears at an overworld box's x/z (NETHER_ENCOUNTERS.md experiment N3).
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import suppress_inherited_spawns as SIS  # noqa: E402

OVERWORLD, NETHER, END = "minecraft:overworld", "minecraft:the_nether", "minecraft:the_end"
FAKE = "data/cobblemon/spawn_pool_world/fake_nether_magby.json"
DETAIL = {"id": "fake-magby", "pokemon": "magby", "type": "pokemon", "spawnablePositionType": "grounded",
          "bucket": "common", "level": "20-30", "weight": 5.0,
          "condition": {"biomes": ["#minecraft:is_nether"]},
          "anticondition": {"isRaining": True}}


def _anti_satisfied(c, dim, x, z):
    """True when anticondition c holds at (dim, x, z), per the 1.8.0 bytecode note."""
    for lo, hi, v in (("minX", "maxX", x), ("minZ", "maxZ", z)):
        if lo in c and v < c[lo]:
            return False
        if hi in c and v > c[hi]:
            return False
    dims = c.get("dimensions")
    if dims and dim not in dims:
        return False
    other = set(c) - {"minX", "maxX", "minZ", "maxZ", "dimensions"}
    assert not other, "the evaluator only models boxes and dimensions: %s" % other
    return True


def _suppressed(detail, dim, x, z):
    return any(_anti_satisfied(c, dim, x, z) for c in detail["anticonditions"] if "isRaining" not in c)


def _route_box_centre():
    b = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"][0]["spawn_scope"]["boxes"][0]
    return (b["min_x"] + b["max_x"]) // 2, (b["min_z"] + b["max_z"]) // 2


def _run(tmp_path):
    server, world, out = tmp_path / "server", tmp_path / "world", tmp_path / "out"
    (server / "mods").mkdir(parents=True)
    world.mkdir()
    with zipfile.ZipFile(server / "mods" / "fake.jar", "w") as z:
        z.writestr(FAKE, json.dumps({"enabled": True, "neededInstalledMods": [], "spawns": [dict(DETAIL)]}))
    assert SIS.main(["--server", str(server), "--world", str(world), "--out", str(out)]) == 0
    doc = json.loads((out / FAKE).read_text(encoding="utf-8"))
    (detail,) = doc["spawns"]
    return detail


def test_a_suppression_box_holds_on_the_overworld_and_nowhere_else(tmp_path):
    detail = _run(tmp_path)
    x, z = _route_box_centre()
    assert _suppressed(detail, OVERWORLD, x, z), "the route box no longer suppresses the overworld"
    assert not _suppressed(detail, NETHER, x, z), "an overworld box suppresses the Nether at the same x/z (N153)"
    assert not _suppressed(detail, END, x, z), "an overworld box suppresses the End at the same x/z (N153)"
    assert not _suppressed(detail, OVERWORLD, -10 ** 6, -10 ** 6), "the suppression reaches outside every box"
    # the detail's own anticondition survives, moved into the plural list
    assert {"isRaining": True} in detail["anticonditions"]
    assert "anticondition" not in detail


def test_every_box_anticondition_names_exactly_the_overworld(tmp_path):
    detail = _run(tmp_path)
    boxes = [c for c in detail["anticonditions"] if "minX" in c]
    assert len(boxes) >= 10, len(boxes)
    bad = [c for c in boxes if c.get("dimensions") != [OVERWORLD]]
    assert not bad, (len(bad), bad[:3])


def test_the_unbound_boxes_of_before_the_fix_are_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(SIS, "box_anticondition",
                        lambda b, dimension=None: {"minX": b[0], "maxX": b[1], "minZ": b[2], "maxZ": b[3]})
    detail = _run(tmp_path)
    x, z = _route_box_centre()
    assert _suppressed(detail, NETHER, x, z), "the check no longer sees the pre-fix fault: it has lost its teeth"


@pytest.mark.parametrize("box", [(0, 15, 32, 47), (-1024, -1009, 9200, 9215)])
def test_box_anticondition_shape(box):
    assert SIS.box_anticondition(box) == {"minX": box[0], "maxX": box[1], "minZ": box[2], "maxZ": box[3],
                                          "dimensions": [OVERWORLD]}
