"""tools/light_plan.py, the after-donor split in tools/place_town.py and tools/reapply.py, and tools/cavern_farms.py.

Written in the same session as the tools (see docs/HANDOVER_CODEX.md review debt): a second reader should check the
light model's pessimism and the scope rules against the game, not only against these tests.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import light_plan as LP  # noqa: E402


def _placements():
    return json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ block rules

def test_opaque_blocks_are_not_see_through():
    # Without this the model lets light through a wall and calls a dark room lit: substring matching once made
    # light-gray wool ("light"), snow blocks ("snow") and froglights see-through.
    for name in ("minecraft:light_gray_wool", "minecraft:snow_block", "minecraft:ochre_froglight",
                 "minecraft:stone_bricks", "minecraft:spruce_planks"):
        assert not LP.see_through(name), name
    for name in ("minecraft:air", "minecraft:glass_pane", "minecraft:oak_fence", "minecraft:lantern",
                 "minecraft:oak_leaves", "minecraft:snow", "minecraft:carrots"):
        assert LP.see_through(name), name


def test_no_spawning_on_slabs_stairs_or_farmland():
    # A monster cannot spawn on a bottom slab, stairs or farmland; counting them would plant needless lights.
    for name in ("minecraft:oak_slab", "minecraft:stone_brick_stairs", "minecraft:farmland", "minecraft:glass"):
        assert not LP.spawn_surface(name), name
    for name in ("minecraft:grass_block", "minecraft:stone", "minecraft:oak_planks"):
        assert LP.spawn_surface(name), name


# ------------------------------------------------------------------ the model

def _room():
    """A closed 9x9 stone room, floor at y=0, 3 high, in a model box."""
    m = LP.Model((0, 0, 10, 10), 0, 6)
    for x in range(11):
        for z in range(11):
            m.set(x, 0, z, "minecraft:stone")
            m.set(x, 4, z, "minecraft:stone")
            if x in (0, 10) or z in (0, 10):
                for y in range(1, 4):
                    m.set(x, y, z, "minecraft:stone")
    return m


def test_light_falls_one_a_block_and_stops_at_walls():
    # The whole tool rests on this: a lantern gives 15 and each step through air costs 1; a wall stops it.
    m = _room()
    m.set(5, 1, 5, "minecraft:lantern")
    L = m.light()
    assert L[5, 1, 5] == 15
    assert L[6, 1, 5] == 14 and L[8, 1, 5] == 12
    assert L[9, 2, 9] == 15 - (4 + 1 + 4)
    assert L[10, 1, 5] == 0                           # inside the wall: opaque cells receive nothing


def test_a_dark_room_has_spawn_cells_and_a_lantern_clears_them():
    m = _room()
    sp = m.spawn_cells()
    assert sp[5, 1, 5] and not sp[5, 3, 5]            # on the floor, not with the ceiling one block over the head
    inside = (slice(1, 10), slice(1, 4), slice(1, 10))  # the roof's top is open sky, not the room
    assert ((m.light() == 0) & sp)[inside].any()
    m.set(5, 1, 5, "minecraft:lantern")
    assert not ((m.light() == 0) & m.spawn_cells())[inside].any()


# ------------------------------------------------------------------ the data it wrote

def test_every_lights_earthwork_runs_after_the_donors():
    # A donor is placed whole, air and all: lights set before it vanish (tableland stop, League, mining town,
    # 2026-09-21). Every light_plan earthwork must be marked to go in the after-donor function.
    doc = _placements()
    lights = [q for q in doc["placements"] if q.get("kind") == "earthwork" and q["id"].endswith("_lights")]
    assert lights, "no lights earthworks: the plan was not run"
    assert all(q.get("after") == "donors" for q in lights), [q["id"] for q in lights if q.get("after") != "donors"]


def test_lights_are_lanterns_on_posts_or_floors_never_hidden_light_blocks():
    # The owner: light it as a town, not with invisible blocks.
    doc = _placements()
    for q in doc["placements"]:
        if q.get("kind") == "earthwork" and (q["id"].endswith("_lights") or q["id"].startswith("displaced_farm")):
            for c in q["commands"]:
                assert "minecraft:light" not in c.replace("minecraft:lightning", ""), (q["id"], c)


def test_the_fields_set_their_crops_after_the_lanterns():
    # A crop checks its light when it or a neighbour is set; a lantern from the same function has not lit anything
    # yet, and 131 of 136 crops broke at once. Crops and their farmland go in the after-donor function.
    doc = _placements()
    ids = {q["id"]: q for q in doc["placements"]}
    ground, crops = ids["displaced_farms"], ids["displaced_farm_crops"]
    assert crops.get("after") == "donors" and not ground.get("after")
    assert not any(k in c for c in ground["commands"] for k in ("carrots", "potatoes", "beetroots", "farmland"))
    assert any("lantern" in c for c in ground["commands"])
    assert sum(1 for c in crops["commands"] if any(k in c for k in ("carrots", "potatoes", "beetroots"))) >= 100
    # nothing that spawns monsters or lets them in: wheat is not planted (it is a spawn condition elsewhere)
    assert not any("wheat" in c for c in crops["commands"])


def test_place_town_puts_after_donor_earthworks_in_their_own_function():
    import place_town as PT
    doc = _placements()
    sid = "sunset_west"
    lights = next(q for q in doc["placements"] if q["id"] == "%s_lights" % sid)
    body = [l for l in lights["commands"] if not l.startswith("#")]
    # the main function must not hold the lights, the after-donor list must
    after = []
    for q in doc["placements"]:
        if q.get("settlement") == sid and q.get("kind") == "earthwork" and q.get("after") == "donors":
            after += q["commands"]
    assert set(body) <= set(after)
    src = (ROOT / "tools" / "place_town.py").read_text(encoding="utf-8")
    assert '"after") == "donors"' in src and "_after_donors.mcfunction" in src
    assert PT is not None


def test_reapply_runs_the_after_donor_step_after_the_donors():
    import reapply as RA
    ids = [s[0] for s in RA.steps()]
    assert "R16" in ids and ids.index("R16") > ids.index("R9")
    r16 = next(s for s in RA.steps() if s[0] == "R16")
    fns = {v for k, v in r16[2] if k == "fn"}
    assert "cobblers:towns/displaced_city_after_donors" in fns
    assert "cobblers:towns/tableland_stop_after_donors" in fns


def test_check_refuses_the_live_world(tmp_path):
    import argparse
    import pytest
    a = argparse.Namespace(world=r"C:\x\cobblers-server\cobblers-10240", settlements=[], source_root=None,
                           server_dir=None, dump=None)
    with pytest.raises(SystemExit):
        LP.cmd_check(a)


def test_connected_air_leaves_out_sealed_pockets(monkeypatch, tmp_path):
    # A void sealed in the rock over the cavern is not the cavern: counting it asked for lights in solid rock.
    m = LP.Model((0, 0, 2, 0), 0, 9)
    plan = tmp_path / "derived" / "cavern"
    plan.mkdir(parents=True)
    (plan / "plan.json").write_text(json.dumps({"cavern": [0, 0, 2, 0]}), encoding="utf-8")
    np.savez(plan / "plan.npz", floor=np.array([[1, 1, 1]]), ceiling=np.array([[5, 5, 5]]), top=np.array([[9, 9, 9]]))
    monkeypatch.setattr(LP, "ROOT", tmp_path)
    col = ["minecraft:stone", "minecraft:stone"] + ["minecraft:air"] * 3 + ["minecraft:stone"] * 2 \
        + ["minecraft:air"] * 2 + ["minecraft:stone"]
    cols = {(x, 0): list(col) for x in range(3)}
    r = LP.connected_air(m, cols)
    assert r[1, 3, 0]                                 # cavern air between floor 1 and ceiling 5
    assert not r[1, 7, 0] and not r[1, 8, 0]          # the pocket at 7-8, sealed by rock at 5-6
