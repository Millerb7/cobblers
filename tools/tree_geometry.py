#!/usr/bin/env python
"""The block set of each bird tree as it is seated, from the prefab templates and the pinned sites. Never from a world.

  elder    kits/structures/prefabs/trees/tree_town/elder_<wood>_<variant>.nbt, seated by data/elder_trees.json
           (the 48 standalone elders) or derived/sites/tree_grove_foothill_woods.json (the 4 grove elders: that file is
           gitignored and may be absent, in which case those 4 are reported UNCOVERED, never guessed)
  themed   kits/structures/prefabs/trees/themed/sapling_<theme>.nbt, seated by data/themed_saplings.json
  world    tools/tree_grove.big_tree("oak", "a", "world"), seated by tools/world_tree.CENTRE and GROUND (the tree is
           generated, not a template: tools/world_tree.py writes it as fill commands)

The seat arithmetic is the one `place template` and tools/themed_saplings.place use: the template's trunk-centre
column lands on (x, ground + 1, z) after the site's rotation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nbt  # noqa: E402
import habitat_spawn_model as M  # noqa: E402

PREFABS = ROOT / "kits" / "structures" / "prefabs" / "trees"
ELDER_PINS = ROOT / "data" / "elder_trees.json"
THEMED_PINS = ROOT / "data" / "themed_saplings.json"
GROVE_SITES = ROOT / "derived" / "sites" / "tree_grove_foothill_woods.json"
# `place template` rotations: (x, z) -> ...
ROT = {"none": lambda x, z: (x, z), "clockwise_90": lambda x, z: (-z, x), "180": lambda x, z: (-x, -z),
       "counterclockwise_90": lambda x, z: (z, -x)}
WINDOW = 48          # blocks kept round the trunk centre: a nest's box reaches 16 and a limb 17 (58 for the world tree)

_CACHE = {}


def _template(path_nbt):
    if path_nbt not in _CACHE:
        _, doc = nbt.load(path_nbt)
        pal = doc["palette"]
        _CACHE[path_nbt] = [(tuple(b["pos"]), pal[b["state"]]["Name"], pal[b["state"]].get("Properties") or {})
                            for b in doc["blocks"]]
    return _CACHE[path_nbt]


def seat(blocks, origin, rot, centre_xz, trunk_centre_local, ground_y, window=WINDOW):
    """World solid set and name map of a template. `trunk_centre_local` is the template's (x, z) of the trunk centre
    column; it lands on `centre_xz`. The template's y 0 sits on ground + 1 - oy (oy = origin[1])."""
    qx, qz = ROT[rot](*trunk_centre_local)
    px, pz = centre_xz[0] - qx, centre_xz[1] - qz
    py = ground_y + 1 - origin[1]
    solid, names = set(), {}
    for (tx, ty, tz), name, props in blocks:
        rx, rz = ROT[rot](tx, tz)
        x, y, z = px + rx, py + ty, pz + rz
        if abs(x - centre_xz[0]) > window or abs(z - centre_xz[1]) > window:
            continue
        if M.solid_name(name, props):
            solid.add((x, y, z))
        names[(x, y, z)] = name
    return solid, names


def elder_pins():
    return {e["id"]: e for e in json.loads(ELDER_PINS.read_text(encoding="utf-8"))["elders"]}


def themed_pins():
    return {s["id"]: s for s in json.loads(THEMED_PINS.read_text(encoding="utf-8"))["saplings"]}


def grove_sites():
    """{(x, z): site} of the grove file, or {} when derived/ is absent."""
    if not GROVE_SITES.is_file():
        return {}
    return {(s["x"], s["z"]): s for s in json.loads(GROVE_SITES.read_text(encoding="utf-8"))["elders"]}


def load(tree_id, nest_xz=None):
    """A dict for one tree, or None when its geometry cannot be built here:
       {id, kind, centre (x, z), ground, solid, names, template}.
    `nest_xz` is the tree's existing nest column, needed only for a grove elder (its site is found by position)."""
    if tree_id in (pins := elder_pins()):
        e = pins[tree_id]
        name = "elder_%s_%s" % (e["species"], e["variant"])
        p = PREFABS / "tree_town" / name
        side = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
        ox, oy, oz = side["trunk_origin"]
        c = side["habitat"]["trunk"][0] // 2
        solid, names = seat(_template(p.with_suffix(".nbt")), (ox, oy, oz), e["rotation"], (e["x"], e["z"]),
                            (ox + c, oz + c), e["ground_y"])
        return {"id": tree_id, "kind": "elder", "centre": (e["x"], e["z"]), "ground": e["ground_y"], "solid": solid,
                "names": names, "template": name, "wood": e["species"]}
    if tree_id in (tp := themed_pins()):
        s = tp[tree_id]
        p = PREFABS / "themed" / ("sapling_%s" % s["theme"])
        side = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
        ox, oy, oz = side["trunk_origin"]
        solid, names = seat(_template(p.with_suffix(".nbt")), (ox, oy, oz), s["rotation"], (s["x"], s["z"]),
                            (ox, oz), s["ground_y"])
        return {"id": tree_id, "kind": "themed", "centre": (s["x"], s["z"]), "ground": s["ground_y"], "solid": solid,
                "names": names, "template": "sapling_%s" % s["theme"], "wood": s["theme"]}
    if nest_xz is not None and nest_xz in (gs := grove_sites()):
        s = gs[nest_xz]
        obj = s["object"].rsplit("/", 1)[1]
        p = PREFABS / "tree_town" / obj
        side = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
        ox, oy, oz = side["trunk_origin"]
        c = side["habitat"]["trunk"][0] // 2
        solid, names = seat(_template(p.with_suffix(".nbt")), (ox, oy, oz), s["rotation"], nest_xz, (ox + c, oz + c),
                            s["ground_y"])
        return {"id": tree_id, "kind": "elder", "centre": nest_xz, "ground": s["ground_y"], "solid": solid,
                "names": names, "template": obj, "wood": obj.split("_")[1]}
    return None


def world_tree():
    """The world tree at Foothill Woods from the generator that places it (deterministic, sha256-seeded)."""
    import tree_grove as TG
    import world_tree as WT
    b, dims = TG.big_tree("oak", "a", "world")
    c = dims["trunk"][0] // 2
    ox, oz, oy = WT.CENTRE[0] - c, WT.CENTRE[1] - c, WT.GROUND + 1
    solid, names = set(), {}
    window = 80
    for (x, y, z), blk in b.blocks.items():
        wx, wy, wz = ox + x, oy + y, oz + z
        if abs(wx - WT.CENTRE[0]) > window or abs(wz - WT.CENTRE[1]) > window:
            continue
        name = blk[0] if isinstance(blk, tuple) else blk
        if M.solid_name(name):
            solid.add((wx, wy, wz))
        names[(wx, wy, wz)] = name
    return {"id": "world_tree_foothill_woods", "kind": "world", "centre": tuple(WT.CENTRE), "ground": WT.GROUND,
            "solid": solid, "names": names, "template": "world_tree.big_tree(oak,a,world)", "wood": "oak",
            "height": dims["height"], "dims": dims}
