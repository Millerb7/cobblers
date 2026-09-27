"""tools/themed_saplings.py: the tool's own invariants that tests/test_themed_saplings.py (the data) does not reach.

Written by the test author, not by the session that wrote the tool (commits db6cb43, 4c7583a, f92517c).

Independent sources: data/themed_saplings.json (the pinned sites: "placed from here after that, so a tree never moves
out from under its nest blocks"), the committed prefab sidecars in kits/structures/prefabs/trees/themed/, and vanilla
`place template` rotation as tests/test_themed_saplings.py writes it from Minecraft's StructureTemplate.transform
(mc_rotate), not the tool's own place()/rotate.

What is asserted: the build path places every tree at its pin (position, ground and rotation) and never re-picks a
site without --repick; nests are ordered bottom-up in every prefab and the low/mid/top labels climb in world y;
`records --write` keeps the status of a nest block whose position is unchanged, resets a moved one to planned, drops a
sapling_ block the tool no longer produces, and leaves every other block untouched.

Not covered: pick_sites itself (it needs the heightmap, the paint manifest and derived/ site files), the prefab
shapes (tests/test_themed_saplings.py checks the committed prefabs), and anything in a world.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import themed_saplings as TS  # noqa: E402
from test_themed_saplings import mc_rotate  # noqa: E402

PINS = json.loads((ROOT / "data" / "themed_saplings.json").read_text(encoding="utf-8"))["saplings"]
MANIFEST = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))
LABELS = ("low", "mid", "top", "extra")


# Without it a prefab's nests come out in drawing order and the labels lie: a block called "low" sits in the crown and
# the in-game audit of "the low nest" checks the wrong block.
def test_nests_are_ordered_bottom_up_in_every_prefab():
    sd = TS.sides()
    for theme in TS.THEMES:
        ys = [n["at"][1] for n in sd[theme]["nests"]]
        assert len(ys) >= 3 and ys == sorted(ys), (theme, ys)


# Without it the committed nest blocks' labels no longer follow height in the world (a rotation or seat that moved y).
def test_the_low_mid_top_labels_climb_in_world_y():
    by_tree = {}
    for b in MANIFEST["blocks"]:
        m = re.fullmatch(r"(sapling_.+)_(low|mid|top|extra)", b["id"])
        if m and b.get("pool") == "cobblers:%s" % m.group(1):
            by_tree.setdefault(m.group(1), {})[m.group(2)] = b["position"]["y"]
    assert set(by_tree) == {p["id"] for p in PINS}, sorted(set(by_tree) ^ {p["id"] for p in PINS})
    for tree, ys in by_tree.items():
        order = [ys[k] for k in LABELS if k in ys]
        assert order == sorted(order) and len(order) >= 3, (tree, ys)


@pytest.fixture
def isolated_build(tmp_path, monkeypatch):
    """TS.main's build path with every external input stubbed: no heightmap, no prefab writes, no site picking."""
    import ground
    import terrain
    picked = []
    monkeypatch.setattr(terrain, "load_from_args", lambda a: (None, {"heightmap": {}}))
    monkeypatch.setattr(ground, "load", lambda *a, **k: (lambda x, z: 64))
    monkeypatch.setattr(TS, "build_prefabs", TS.sides)             # the committed sidecars; never rewrite kits/
    monkeypatch.setattr(TS, "pick_sites", lambda *a, **k: picked.append(1) or ([], []))
    monkeypatch.setattr(TS, "FUNCTION", tmp_path / "themed_saplings.mcfunction")
    monkeypatch.setattr(TS, "SITES_OUT", tmp_path / "themed_saplings.json")
    monkeypatch.setattr(TS, "ROOT", tmp_path.parent)                # FUNCTION.relative_to(ROOT) must hold
    return tmp_path, picked


# Without it a build re-picks the sites (a changed heightmap or rule moves a tree out from under its 42 nest blocks), or
# seats a tree somewhere other than its pin: another x/z, another ground, another rotation.
def test_the_build_places_every_tree_at_its_pin_and_never_repicks(isolated_build):
    tmp, picked = isolated_build
    assert TS.main([]) == 0
    assert picked == [], "pick_sites ran without --repick"
    lines = (tmp / "themed_saplings.mcfunction").read_text(encoding="utf-8").splitlines()
    sd = TS.sides()
    for p in PINS:
        side = sd[p["theme"]]
        ox, oy, oz = side["trunk_origin"]
        qx, qz = mc_rotate(ox, oz, p["rotation"])
        want = "place template %s %d %d %d %s none 1.0 0" % (side["template_id"], p["x"] - qx, p["ground_y"] + 1 - oy,
                                                              p["z"] - qz, p["rotation"])
        assert want in lines, (p["id"], want)
    trees = [l for l in lines if l.startswith("place template cobblers:kits/trees/themed/sapling_")]
    assert len(trees) == len(PINS), len(trees)
    sites = json.loads((tmp / "themed_saplings.json").read_text(encoding="utf-8"))
    assert sites["saplings"] == PINS


def _write_records(tmp_path, monkeypatch, doc):
    path = tmp_path / "habitat_blocks.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(TS, "MANIFEST", path)
    assert TS.main(["records", "--write"]) == 0
    return json.loads(path.read_text(encoding="utf-8"))["blocks"]


# Without it `records --write` resets every placed nest to planned (the verify then skips them all), keeps "placed" on a
# block the tool has moved (the verify looks for it where it is not), keeps a stale block, or disturbs other blocks.
def test_records_write_keeps_placed_status_only_where_the_position_is_unchanged(tmp_path, monkeypatch):
    doc = copy.deepcopy(MANIFEST)
    sap = [b for b in doc["blocks"] if b["id"].startswith("sapling_")]
    others = [b for b in doc["blocks"] if not b["id"].startswith("sapling_")]
    assert len(sap) >= 42 and len(others) >= 100, (len(sap), len(others))
    for b in sap:
        b["status"] = "placed"
    moved = sap[0]["id"]
    sap[0]["position"] = dict(sap[0]["position"], y=sap[0]["position"]["y"] + 7)
    doc["blocks"].append(dict(copy.deepcopy(sap[1]), id="sapling_retired_tree_low"))
    got = _write_records(tmp_path, monkeypatch, doc)
    assert got[:len(others)] == others, "a non-sapling block changed or moved"
    new = {b["id"]: b for b in got[len(others):]}
    assert "sapling_retired_tree_low" not in new
    assert set(new) == {b["id"] for b in sap}
    assert new[moved]["status"] == "planned", new[moved]
    assert new[moved]["position"] == next(b for b in MANIFEST["blocks"] if b["id"] == moved)["position"]
    assert all(b["status"] == "placed" for i, b in new.items() if i != moved)
