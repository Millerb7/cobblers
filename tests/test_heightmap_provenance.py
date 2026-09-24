"""The heightmap's provenance keys are documented and owned.

Every pass records the file it consumed under its own key in data/world.json. On 2026-09-22 a new pass read
`sculpted_from` assuming it meant "the map before my sculpt"; it means "the river cut tools/sculpt.py consumed",
three passes older, and tools/paint_maps.py and tools/validate_data.py both depend on that meaning. The tool
worked against stale terrain and only the empty basin gave it away.

These tests make the next collision loud: a key in world.json that the documentation does not name, or a
documented key no longer in world.json, fails.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "world-building" / "HEIGHTMAP_PROVENANCE.md"
WORLD = ROOT / "data" / "world.json"


def _documented():
    text = DOC.read_text(encoding="utf-8")
    return {m.group(1) for m in re.finditer(r"^\| `([a-z0-9_]+)` \|", text, re.M)}


def test_every_provenance_key_in_world_json_is_documented():
    hm = json.loads(WORLD.read_text(encoding="utf-8"))["heightmap"]
    doc = _documented()
    assert doc, "the provenance table is empty: the check would pass on nothing"
    undocumented = sorted(set(hm) - doc)
    assert not undocumented, (
        "keys in data/world.json heightmap that %s does not explain: %s. Add a row naming what the key means and "
        "which tool owns it, so the next pass cannot reuse it by accident." % (DOC.name, undocumented))


def test_every_documented_key_still_exists():
    hm = json.loads(WORLD.read_text(encoding="utf-8"))["heightmap"]
    stale = sorted(_documented() - set(hm))
    assert not stale, "%s documents keys world.json no longer has: %s" % (DOC.name, stale)


def test_each_recorded_input_names_a_different_file_than_the_current_one():
    # A pass that recorded the canonical file as its own input would re-derive from its own output.
    hm = json.loads(WORLD.read_text(encoding="utf-8"))["heightmap"]
    for key, v in hm.items():
        if isinstance(v, dict) and "path" in v and "sha256" in v:
            assert v["path"] != hm["path"], "%s records the current heightmap as its own input" % key
            assert v["sha256"] != hm["sha256"], "%s records the current hash as its own input" % key


def test_the_rift_sculpt_does_not_reuse_another_passes_key():
    # The specific mistake: rift_heightmap.py must read its own key, never sculpted_from.
    src = (ROOT / "tools" / "rift_heightmap.py").read_text(encoding="utf-8")
    assert 'get("rift_sculpted_from")' in src
    assert 'get("sculpted_from")' not in src, "rift_heightmap.py is reading tools/sculpt.py's key again"


def test_the_ceiling_the_doc_states_is_the_one_world_json_sets():
    world = json.loads(WORLD.read_text(encoding="utf-8"))
    text = DOC.read_text(encoding="utf-8")
    assert "y10..y310" in text and str(world["vertical"]["max_y"]) == "310"
    spec = json.loads((ROOT / "data" / "rift_sculpt.json").read_text(encoding="utf-8"))
    assert spec["ceiling"]["world_max_y"] == world["vertical"]["max_y"]
