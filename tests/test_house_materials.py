"""A house placed in other materials: tools/place_town.py rewrite_template renames the palette like for like, in a copy
written to the build pack (never to kits/, the Repurposed Structures houses it is used on are not ours to commit), and
every record that names a material set names one data/rematerial.json has. Without it, the Displaced City's repeated
designs would stand as exact copies and Surge's houses in Sabrina's stone."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import nbt  # noqa: E402
import place_town as PT  # noqa: E402

BASE = ROOT / "kits" / "structures" / "campaign" / "f4" / "pallet" / "buildings" / "small1.nbt"


def names(path):
    _, doc = nbt.load(path)
    pal = doc["palette"]
    return Counter(pal[b["state"]]["Name"] for b in doc["blocks"])


def test_a_rewritten_copy_swaps_the_named_blocks_and_nothing_else(tmp_path):
    before = names(BASE)
    swap = next(n for n in before if n.endswith("_planks"))
    dest = tmp_path / "copy.nbt"
    PT.rewrite_template(BASE, dest, materials={swap: "minecraft:cherry_planks"})
    after = names(dest)
    assert swap not in after
    assert after["minecraft:cherry_planks"] == before[swap] + before.get("minecraft:cherry_planks", 0)
    assert sum(after.values()) == sum(before.values())
    assert {n: c for n, c in after.items() if n != "minecraft:cherry_planks"} == \
           {n: c for n, c in before.items() if n not in (swap, "minecraft:cherry_planks")}


def test_every_named_material_set_exists_and_maps_blocks_to_blocks():
    sets = json.loads((ROOT / "data" / "rematerial.json").read_text(encoding="utf-8")).get("house_sets") or {}
    for sid, s in sets.items():
        assert s.get("why"), sid
        assert all(a.startswith("minecraft:") and b.startswith("minecraft:") and a != b for a, b in s["map"].items()), sid
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    for q in doc["placements"]:
        m = q.get("materials")
        if isinstance(m, str):
            assert m in sets, "%s names material set %s" % (q["id"], m)
