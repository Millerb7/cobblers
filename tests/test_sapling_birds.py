"""Route 1's sapling birds: habitat route_1_sapling_crown (data/spawns.json), its Habitat Block (data/habitat_blocks.json
route1_sapling_crown) and the pool tools/compile_spawns.py compiles for it.

Written by the test author, not by the session that authored the habitat.

What is asserted: the habitat is Pidgey and Hoothoot at levels 5-8, both from Route 1's own roster
(route_species_selection.route_01_pallet_to_brock); the Habitat Block names that habitat's pool, sits at (1380, 147,
4628) with range 14 (at least the prefab's crown radius, as its "why" claims), and is an oak_log cell of the sapling
prefab placed the way tools/maze_forest.py places it (origin from maze_forest.SAPLING, the prefab's trunk_origin and
trunk, and the rounded heightmap ground, tools/ground.py); compile_spawns.build writes the habitat pool with exactly
those two species at 5-8.

The heightmap is outside the repository (COBBLERS_SOURCE_ROOT); without it the in-the-trunk test SKIPs, and a skip is
not a pass.

Not covered, and it needs a running server: whether the block's reach is a sphere or a column (EXP-033), whether a
bird spawns perched on leaves, and whether the block is live after its chunk reloads (EXP-021).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_spawns as CS  # noqa: E402
import nbt  # noqa: E402

SPAWNS = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
ROUTES = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
HABITAT = next((h for h in SPAWNS["habitats"] if h["id"] == "route_1_sapling_crown"), None)
BLOCK = next((b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
              if b["id"] == "route1_sapling_crown"), None)
PREFAB = ROOT / "kits" / "structures" / "prefabs" / "trees" / "tree_town" / "sapling_oak_a"
SIDE = json.loads(PREFAB.with_suffix(".json").read_text(encoding="utf-8"))
BIRDS = {"pidgey", "hoothoot"}      # the owner's playtest, 2026-09-24: Route 1's own birds


# Without it the habitat is renamed or dropped and the Habitat Block points at a pool nobody authors.
def test_the_sapling_crown_habitat_and_block_exist():
    assert HABITAT is not None and BLOCK is not None


# Without it the sapling gets a species Route 1 does not have (a coast bird, an evolved form) or a level off the
# meadow's band, which is a balance change nobody signed.
def test_the_sapling_birds_are_route_1s_pidgey_and_hoothoot_at_5_to_8():
    assert {e["pokemon"] for e in HABITAT["entries"]} == BIRDS
    assert HABITAT["level_band"] == {"minimum": 5, "maximum": 8}
    assert all(e["level"] == "5-8" for e in HABITAT["entries"])
    roster = set(SPAWNS["route_species_selection"]["route_01_pallet_to_brock"]["species"])
    assert BIRDS <= roster, sorted(BIRDS - roster)


# Without it the block is moved off the sapling, shrunk so the crown is out of reach, or its pool renamed.
def test_the_block_names_the_habitats_pool_and_reaches_the_crown():
    assert BLOCK["pool"] == "cobblers:%s" % HABITAT["id"]
    assert (BLOCK["position"]["x"], BLOCK["position"]["y"], BLOCK["position"]["z"]) == (1380, 147, 4628)
    assert BLOCK["range_of_influence"] == 14
    assert BLOCK["range_of_influence"] >= SIDE["habitat"]["crown_radius"]


@pytest.fixture(scope="module")
def placed():
    import ground as G
    import terrain as T
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the sapling's seat comes from the canonical heightmap")
    try:
        g = G.Ground()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)
    import maze_forest
    sx, sz = maze_forest.SAPLING
    ox, oy, oz = SIDE["trunk_origin"]
    c = SIDE["habitat"]["trunk"][0] // 2
    x0, z0, y0 = sx - c - ox, sz - c - oz, g(sx, sz) + 1 - oy
    _, doc = nbt.load(PREFAB.with_suffix(".nbt"))
    pal = doc["palette"]
    out = {(x0 + b["pos"][0], y0 + b["pos"][1], z0 + b["pos"][2]): pal[b["state"]]["Name"] for b in doc["blocks"]}
    assert len(out) > 1000, "the prefab is nearly empty"
    return out


# Without it the block is in the open (a player breaks it walking the clearing, or it floats in air where the trunk is
# not), which the "why" rules out: hidden in the trunk.
def test_the_block_is_inside_the_trunk_as_placed(placed):
    p = (BLOCK["position"]["x"], BLOCK["position"]["y"], BLOCK["position"]["z"])
    assert placed.get(p) == "minecraft:oak_log", placed.get(p)


# Without it the pool compiles empty (the habitat authored but no compiled entries reach it) and the Habitat Block,
# with ReplaceSpawns, turns the sapling into a place where nothing spawns at all.
def test_the_compiled_sapling_pool_holds_pidgey_and_hoothoot():
    files, _routes, _habitats = CS.build(SPAWNS, ROUTES)
    key = "data/cobblers/habitat_pools/%s.json" % HABITAT["id"]
    assert key in files
    spawns = json.loads(files[key])["spawns"]
    assert {s["species"].lower() for s in spawns} == BIRDS, spawns
    assert all(s["levelRange"] == "5-8" for s in spawns), spawns
