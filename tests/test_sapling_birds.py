"""Route 1's sapling nest: habitat route_1_sapling_crown (data/spawns.json), its two activated Habitat Blocks
(data/habitat_blocks.json route1_sapling_low and route1_sapling_crown) and the pool tools/compile_spawns.py compiles
for it.

Written by the test author, not by the session that authored the habitat or the blocks.

Independent sources: the owner, 2026-09-26 (docs/world-building/SAPLING_BIRDS.md status: "at least 20", "Route 1 is
Pidgey only"; the request to raise the spawns, recorded in docs/STATE.md and commit ab3cf01: two blocks in the Route 1
sapling at y134 and y150, up to 12 each, refilling 2 at a time); Route 1's own roster
(route_species_selection.route_01_pallet_to_brock); the sapling prefab (kits/structures/prefabs/trees/tree_town/
sapling_oak_a) placed the way tools/maze_forest.py places it (origin from maze_forest.SAPLING, the prefab's
trunk_origin and trunk, and the rounded heightmap ground, tools/ground.py).

What is asserted: the habitat is Pidgey alone at 5-8, from Route 1's roster, with no time condition; exactly two
blocks name its pool, activated, replace_spawns false, on the sapling's trunk centre at y134 and y150, with up to 12
each (24 in the tree, at least the owner's 20), refilling 2 at a time, spawn_range 16, mimic oak_log; as seated, each
block's cell and its six face neighbours are oak_log (buried in the trunk), and the trunk's log column is one run
whose ends bracket both blocks (the "why" quotes log y124-154 as read on staging; the prefab as seated gives
y123-155); compile_spawns.build writes the pool with Pidgey alone at 5-8.

The heightmap is outside the repository (COBBLERS_SOURCE_ROOT); without it the in-the-trunk tests SKIP, and a skip is
not a pass.

Not covered, and it needs a running server: that the blocks are in the world, that Pidgey spread up the tree rather
than settling on the clearing floor, whether 12 per block are held under real mob caps, whether a bird stands on
leaves, and whether an activated block survives a chunk reload.
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
ALL_BLOCKS = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
HABITAT = next((h for h in SPAWNS["habitats"] if h["id"] == "route_1_sapling_crown"), None)
POOL = "cobblers:route_1_sapling_crown"
BLOCKS = {b["id"]: b for b in ALL_BLOCKS if b.get("pool") == POOL}
PREFAB = ROOT / "kits" / "structures" / "prefabs" / "trees" / "tree_town" / "sapling_oak_a"
SIDE = json.loads(PREFAB.with_suffix(".json").read_text(encoding="utf-8"))
BIRD = "pidgey"                                            # the owner, 2026-09-26: "Route 1 is Pidgey only"
NEST_Y = {"route1_sapling_low": 134, "route1_sapling_crown": 150}   # the stated heights (docs/STATE.md: y134, y150)
MIMIC = "minecraft:oak_log"
FACES = ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


# Without it the habitat is renamed or dropped and the nest blocks point at a pool nobody authors.
def test_the_sapling_habitat_exists():
    assert HABITAT is not None and HABITAT["mechanism"] == "habitat_block"


# Without it the sapling gets a second species (Hoothoot back, a coast bird, an evolved form), a level off the
# meadow's band, or a night-only condition that empties the nest by day.
def test_the_sapling_bird_is_route_1s_pidgey_alone_at_5_to_8_by_day_and_night():
    assert [e["pokemon"] for e in HABITAT["entries"]] == [BIRD]
    assert HABITAT["level_band"] == {"minimum": 5, "maximum": 8}
    assert all(e["level"] == "5-8" for e in HABITAT["entries"])
    assert not any((e.get("conditions") or {}).get("timeRange") for e in HABITAT["entries"])
    roster = set(SPAWNS["route_species_selection"]["route_01_pallet_to_brock"]["species"])
    assert BIRD in roster


# Without it a nest block goes missing, a third appears, one is moved off the trunk centre or to another height, the
# tree ends up holding fewer than the owner's 20 birds, or the blocks drop back to the smaller nest (10 alive, 1 per
# refill) the owner asked to raise.
def test_two_activated_blocks_on_the_trunk_at_y134_and_y150_holding_at_least_20():
    import maze_forest
    sx, sz = maze_forest.SAPLING
    assert set(BLOCKS) == set(NEST_Y), sorted(BLOCKS)
    for bid, y in NEST_Y.items():
        b = BLOCKS[bid]
        assert (b["position"]["x"], b["position"]["y"], b["position"]["z"]) == (sx, y, sz), (bid, b["position"])
        assert b["style"] == "activated" and b["replace_spawns"] is False, bid
        assert b["mimic"] == MIMIC, (bid, b["mimic"])
        a = b["activated"]
        assert (a["max_spawns"], a["max_spawns_per_activation"], a["spawn_range"], a["trigger"], a["chance"],
                a["cancel_range"]) == (12, 2, 16, "TICK", 1.0, -1), (bid, a)
    assert sum(BLOCKS[b]["activated"]["max_spawns"] for b in NEST_Y) >= 20
    assert not any(b["id"] == "route1_sapling_crown" and b["style"] == "natural" for b in ALL_BLOCKS)


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


# Without it a block is in the open (a player breaks it walking the branches, or it floats where the trunk is not):
# each block and its six face neighbours must be the trunk's oak log, which is also what the mimic setblock writes.
def test_each_block_is_buried_in_the_trunk_as_placed(placed):
    for bid in NEST_Y:
        p = BLOCKS[bid]["position"]
        got = [placed.get((p["x"] + dx, p["y"] + dy, p["z"] + dz)) for dx, dy, dz in FACES]
        assert all(g == MIMIC for g in got), (bid, got)


# Without it the trunk the "why" describes (log y124-154) is not the trunk the prefab builds: the low block would sit
# below the clearing floor or the crown block above the trunk's top.
def test_the_trunk_log_column_brackets_both_blocks(placed):
    import maze_forest
    sx, sz = maze_forest.SAPLING
    ys = sorted(y for (x, y, z), n in placed.items() if (x, z) == (sx, sz) and n == MIMIC)
    assert ys == list(range(ys[0], ys[-1] + 1)), "the trunk centre column is not one log run"
    # on the heightmap's ground (124) the prefab's centre column is log y123-155 (y123-124 under ground); the "why"
    # quotes y124-154 as read on staging, one lower at the top: only the bracketing is asserted, not either number
    assert ys[0] < min(NEST_Y.values()) and max(NEST_Y.values()) < ys[-1], (ys[0], ys[-1])


# Without it the pool compiles empty (a nest that never holds a bird) or with a second species.
def test_the_compiled_sapling_pool_is_pidgey_alone():
    files, _routes, _habitats = CS.build(SPAWNS, ROUTES)
    key = "data/cobblers/habitat_pools/%s.json" % HABITAT["id"]
    assert key in files
    spawns = json.loads(files[key])["spawns"]
    assert [s["species"] for s in spawns] == [BIRD], spawns
    assert all(s["levelRange"] == "5-8" and "timeRange" not in s for s in spawns), spawns
