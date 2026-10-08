"""tools/suppress_inherited_spawns.py: every inherited spawn is removed in the Nether, and the overworld is unchanged.

The owner approved "replace, not layer" for the Nether (docs/mechanics/NETHER_ENCOUNTERS.md Q3, 2026-10-08). The tool adds
ONE anticondition {"dimensions": ["minecraft:the_nether"]} to every inherited detail, and keeps its suppression boxes
plain (no dimension): review N153's per-box overworld binding was reverted because it grew the pack from 240.8 MB to
418.8 MB (relayed from that unit) and the Nether anticondition leaves the binding nothing to protect.

Independent source: the Cobblemon 1.8.0 bytecode read on 2026-10-08 (docs/research/notes/
spawn-dimension-condition-1.8.0.md). SpawningCondition.fits returns false when "dimensions" is non-null, non-empty and
does not contain world.dimension().location(); coordinate bounds that are absent restrict nothing; SpawnDetail.isSatisfiedBy
drops a detail when ANY of its anticonditions is satisfied. `_anti_satisfied` below is that rule written from the note,
not from the tool, and the box under test is read from data/routes.json directly, not from the tool's merged set.

The mutation tests change the GENERATOR (the tool's NETHER_ANTICONDITION and box_anticondition), never the fixture.

Not covered, and it needs a running server: that Cobblemon loads the anticondition and /checkspawn in the Nether lists
no inherited species (NETHER_ENCOUNTERS.md experiment N3).
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
OURS = "data/cobblers/spawn_pool_world/nether/nether_wastes_near.json"
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


def _run(tmp_path, *extra, ours=False):
    server, world, out = tmp_path / "server", tmp_path / "world", tmp_path / "out"
    (server / "mods").mkdir(parents=True)
    world.mkdir()
    with zipfile.ZipFile(server / "mods" / "fake.jar", "w") as z:
        z.writestr(FAKE, json.dumps({"enabled": True, "neededInstalledMods": [], "spawns": [dict(DETAIL)]}))
    if ours:
        # our compiled spawn pack, installed in the world's datapacks as reapply.py install puts it
        f = world / "datapacks" / "cobblers_spawns" / OURS
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps({"enabled": True, "spawns": [dict(DETAIL, id="ours", condition={"dimensions": [NETHER]})]}),
                     encoding="utf-8")
    assert SIS.main(["--server", str(server), "--world", str(world), "--out", str(out), *extra]) == 0
    doc = json.loads((out / FAKE).read_text(encoding="utf-8"))
    (detail,) = doc["spawns"]
    return detail, out


def test_every_inherited_spawn_is_gone_in_the_nether_and_the_overworld_keeps_its_suppression(tmp_path):
    detail, _ = _run(tmp_path)
    x, z = _route_box_centre()
    assert _suppressed(detail, OVERWORLD, x, z), "the route box no longer suppresses the overworld"
    assert not _suppressed(detail, OVERWORLD, -10 ** 6, -10 ** 6), "the suppression reaches outside every box"
    for at in ((x, z), (-10 ** 6, -10 ** 6), (5000, 5000)):
        assert _suppressed(detail, NETHER, *at), "an inherited spawn survives in the Nether at %s" % (at,)
    # the detail's own anticondition survives, moved into the plural list
    assert {"isRaining": True} in detail["anticonditions"]
    assert "anticondition" not in detail


def test_exactly_one_nether_anticondition_and_plain_boxes(tmp_path):
    detail, _ = _run(tmp_path)
    boxes = [c for c in detail["anticonditions"] if "minX" in c]
    assert len(boxes) >= 10, len(boxes)
    assert not [c for c in boxes if "dimensions" in c], "a box carries a dimension again (the 419 MB shape)"
    assert [c for c in detail["anticonditions"] if "dimensions" in c] == [{"dimensions": [NETHER]}]


def test_the_overworld_is_unchanged_by_the_nether_rule(tmp_path):
    """--no-nether is the pack as it was before 2026-10-08: the only difference is the one Nether anticondition."""
    after, _ = _run(tmp_path / "a")
    before, _ = _run(tmp_path / "b", "--no-nether")
    assert after["anticonditions"][:-1] == before["anticonditions"]
    assert after["anticonditions"][-1] == {"dimensions": [NETHER]}
    x, z = _route_box_centre()
    for at in ((x, z), (-10 ** 6, -10 ** 6), (4096, 4096)):
        for dim in (OVERWORLD, END):
            assert _suppressed(after, dim, *at) == _suppressed(before, dim, *at), (dim, at)


def test_our_compiled_pools_are_never_re_emitted(tmp_path):
    """Contract C19: the suppression reads no cobblers_* pack, so our own Nether tables are not stripped."""
    _, out = _run(tmp_path, ours=True)
    assert not (out / OURS).exists(), "the suppression re-emitted (and so stripped) our own compiled Nether pool"
    assert not list(out.glob("data/cobblers/**/*.json"))


def test_a_nether_rule_bound_to_the_overworld_is_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(SIS, "NETHER", OVERWORLD)
    detail, _ = _run(tmp_path)
    assert not _suppressed(detail, NETHER, -10 ** 6, -10 ** 6), "the check no longer sees a mis-bound rule"


def test_a_missing_nether_rule_is_caught(tmp_path, monkeypatch):
    real = SIS.suppress
    monkeypatch.setattr(SIS, "suppress", lambda doc, conds, nether=True: real(doc, conds, nether=False))
    detail, _ = _run(tmp_path)
    assert not _suppressed(detail, NETHER, -10 ** 6, -10 ** 6), "the check no longer sees a missing rule"


@pytest.mark.parametrize("box", [(0, 15, 32, 47), (-1024, -1009, 9200, 9215)])
def test_box_anticondition_shape(box):
    assert SIS.box_anticondition(box) == {"minX": box[0], "maxX": box[1], "minZ": box[2], "maxZ": box[3]}
