"""The independent audit of the eight gym arenas (tools/gym_arenas_audit.py), and the findings it holds open.

Two halves. The SYNTHETIC tests pin the audit's own models to hand-computed answers on tiny worlds, so a regression in
the replay, the walk, the fluids, the light or the bone pose shows up without the heightmap or a jar. The INTEGRATION
tests replay the real generated functions (built here into a temporary directory) over the real ground and the real
jars, one test per property per gym; a defect the audit found in the content is a strict xfail that names it, so it
stays visible and turns red the day it is fixed without the xfail being removed.

What this does NOT cover: anything at runtime. That Battle Positions puts a Pokemon on its block, that rctmod starts a
battle on sight, that a player in a real client is stopped by a lantern or can crouch under it, that light renders as
modelled: those are experiments in a running server, not pytest.
"""
from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import gym_arenas_audit as A  # noqa: E402


# ============================================================================================ synthetic worlds
class Flat:
    """Nature for a synthetic world: rock at and under `top`, air over it, no water, no lot."""

    def __init__(self, top=-100):
        self.top = top
        self.water_level = lambda x, z: 0

    def __call__(self, x, y, z):
        return A.NAT if y <= self.top else A.NAT_AIR

    def column(self, x, z):
        return self.top, None, 0

    def natural_top(self, x, z):
        return self.top, False


def world(top=-100, cells=None):
    w = A.World(Flat(top))
    for c, st in (cells or {}).items():
        w.set(c, st, "test")
    return w


def run(w, *lines):
    log = {}
    for line in lines:
        A.apply_line(w, line, "test", log)
    return log


BOX = (-6, -6, -6, 6, 20, 6)


# ---------------------------------------------------------------------------------------------- the replay
def test_fill_modes_replay_like_vanilla():
    # Removing this lets a hollow, outline, keep or filtered fill be replayed as a plain one, and every later check
    # reads a world the server never builds.
    w = world()
    run(w, "fill 0 0 0 2 2 2 minecraft:stone hollow")
    assert sum(1 for c in w.cells.values() if c == "minecraft:stone") == 26
    assert w.get(1, 1, 1) == "minecraft:air" and w.written((1, 1, 1))
    run(w, "fill 0 0 0 2 2 2 minecraft:dirt replace minecraft:stone")
    assert sum(1 for c in w.cells.values() if c == "minecraft:dirt") == 26
    run(w, "fill 0 0 0 2 2 2 minecraft:glass keep")
    assert w.get(1, 1, 1) == "minecraft:glass" and w.get(0, 0, 0) == "minecraft:dirt"
    run(w, "fill 5 0 0 7 2 2 minecraft:stone outline")
    assert not w.written((6, 1, 1)) and w.get(5, 0, 0) == "minecraft:stone"
    run(w, "setblock 1 1 1 minecraft:stone keep")
    assert w.get(1, 1, 1) == "minecraft:glass"


def test_execute_guards_are_evaluated_against_the_model():
    # Removing this lets the seat move be replayed unconditionally: a move whose guard can never pass in the world
    # (the 'trainer_marker_toward_dais' mutation) would look done.
    w = world(cells={(0, 0, 0): "minecraft:dirt"})
    run(w, "execute if block 0 0 0 minecraft:dirt positioned 0.5 0 0.5 unless entity @a[distance=..17] "
           "run setblock 9 9 9 minecraft:stone",
        "execute unless block 0 0 0 minecraft:dirt run setblock 8 8 8 minecraft:stone")
    assert w.get(9, 9, 9) == "minecraft:stone"
    assert not w.written((8, 8, 8))
    with pytest.raises(A.Unsupported):
        run(w, "clone 0 0 0 1 1 1 5 5 5")


# ---------------------------------------------------------------------------------------------- the walk
def test_a_one_block_ledge_takes_a_jump_and_two_blocks_take_none():
    # Removing this lets the walk climb walls (a softlock passes) or refuse a ledge every player jumps.
    w = world(top=0, cells={(1, 1, 0): "minecraft:stone", (0, 1, 2): "minecraft:stone",
                            (0, 2, 2): "minecraft:stone"})
    jump, walk = A.Walker(w, BOX), A.Walker(w, BOX, jump=False)
    start = (0, 0, 1.0)
    assert (1, 0, 2.0) in jump.reach(start)
    assert (1, 0, 2.0) not in walk.reach(start)
    assert (0, 2, 3.0) not in jump.reach(start)


def test_a_stair_is_walked_up_from_its_low_side_and_jumped_from_its_high_side():
    # Removing this loses the difference between a flight of stairs (two half steps a tread) and a wall of full
    # blocks, which is what the 'tread_dropped' mutation turns a newel stair into.
    low = world(top=0, cells={(1, 1, 0): "minecraft:stone_brick_stairs[facing=east,half=bottom]"})
    high = world(top=0, cells={(1, 1, 0): "minecraft:stone_brick_stairs[facing=west,half=bottom]"})
    west = (-6, -6, -6, 1, 20, 6)   # the walk kept west of the stair's far side, so only its near side is offered
    assert (1, 0, 2.0) in A.Walker(low, west, jump=False).reach((0, 0, 1.0))
    assert (1, 0, 2.0) not in A.Walker(high, west, jump=False).reach((0, 0, 1.0))
    assert (1, 0, 2.0) in A.Walker(high, west).reach((0, 0, 1.0))


def test_a_fall_over_three_is_refused_unless_it_lands_in_water():
    # Removing this lets a descent that hurts (or a one-way drop) pass as a walk.
    pillar = {(0, y, 0): "minecraft:stone" for y in range(1, 5)}            # top at 5: a drop of 4 to the floor
    w = world(top=0, cells=pillar)
    assert (1, 0, 1.0) not in A.Walker(w, BOX).reach((0, 0, 5.0))
    assert (1, 0, 1.0) in A.Walker(w, BOX, fall=1e9).reach((0, 0, 5.0))
    three = world(top=0, cells={(0, y, 0): "minecraft:stone" for y in range(1, 4)})
    assert (1, 0, 1.0) in A.Walker(three, BOX).reach((0, 0, 4.0))
    wet = dict(pillar)
    wet[(1, 1, 0)] = "minecraft:water"
    assert (1, 0, 1.0) in A.Walker(world(top=0, cells=wet), BOX).reach((0, 0, 5.0))


def test_a_lantern_hung_three_over_a_tread_stops_an_upright_player_on_the_flight():
    # Removing this lets the walk pass through hanging lanterns, which is how gym 7's adit passed its builder's check.
    # The flight runs south and down: tread A top 4, tread B top 3; the body crosses the boundary on A's low half
    # (3.5), so an upright head reaches 5.3 and meets the lantern's 5.0625; crouching (1.5) it reaches 5.0.
    w = world(cells={(0, 3, 0): "minecraft:stone_brick_stairs[facing=north,half=bottom]",
                     (0, 2, 1): "minecraft:stone_brick_stairs[facing=north,half=bottom]",
                     (0, 5, 1): "minecraft:lantern[hanging=true]"})
    start, foot = (0, 0, 4.0), (0, 1, 3.0)
    assert foot not in A.Walker(w, BOX).reach(start)
    assert foot in A.Walker(w, BOX, body=1.5).reach(start)
    assert start not in A.Walker(w, BOX).reach(foot)
    w.set((0, 5, 1), "minecraft:air", "test")
    assert foot in A.Walker(w, BOX).reach(start)
    assert start in A.Walker(w, BOX, jump=False).reach(foot)


# ---------------------------------------------------------------------------------------------- fluids, light
def test_water_flows_into_air_but_not_through_a_door_or_out_of_settled_world_water():
    # Removing this lets a channel that spills, or a door that would hold it, be judged wrong.
    w = world(top=0, cells={(0, 1, 0): "minecraft:water", (1, 1, 0): "minecraft:air",
                            (0, 1, 1): "minecraft:dark_oak_door[open=true]", (0, 1, 2): "minecraft:air"})
    wet = A.flow(w, (-3, 0, -3, 3, 3, 3), [(0, 1, 0)], 7)
    assert (1, 1, 0) in wet
    assert (0, 1, 1) not in wet and (0, 1, 2) not in wet
    lake = A.World(Flat(top=0))
    lake.nature.water_level = lambda x, z: 1 if x == 0 else 0
    nat = A.flow(lake, (-3, 0, -3, 3, 3, 3), [(0, 1, 0)], 7)
    assert (1, 1, 0) not in nat     # settled: the world's own water does not move into ground it already sits beside


def test_block_light_falls_one_a_block_and_stops_at_an_opaque_cube():
    # Removing this lets a buried lantern (gym 1's newel) count as lighting the stair round it.
    w = world(cells={(0, 0, 0): "minecraft:lantern"})
    lit = A.block_light(w, (-20, -20, -20, 20, 20, 20))
    assert lit[(1, 0, 0)] == 14 and lit[(3, 0, 0)] == 12 and lit.get((15, 0, 0), 0) == 0
    boxed = world(cells={(0, 0, 0): "minecraft:lantern", **{(dx, dy, dz): "minecraft:stone" for dx, dy, dz in (
        (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))}})
    assert A.block_light(boxed, (-20, -20, -20, 20, 20, 20)).get((2, 0, 0), 0) == 0


# ---------------------------------------------------------------------------------------------- sizes
def test_a_bone_turned_minus_90_about_x_swings_a_forward_limb_down():
    # Removing this lets the model sweep use the wrong sign: Cobblemon's TexturedModel builds each part in the file's
    # frame with y negated and turns it Rz Ry Rx, which in the file's frame is Rz(-z) Ry(y) Rx(-x). A +z limb turned
    # -90 about x points DOWN (top 0, radius sqrt 2); the unconjugated reading points it up (top 16).
    geo = {"minecraft:geometry": [{"bones": [
        {"name": "root", "pivot": [0, 0, 0]},
        {"name": "arm", "parent": "root", "pivot": [0, 0, 0], "rotation": [-90, 0, 0],
         "cubes": [{"origin": [0, 0, 0], "size": [1, 1, 16]}]}]}]}
    r, top = A.model_extent(geo)
    assert abs(r - math.sqrt(2)) < 1e-9 and abs(top - 0.0) < 1e-9
    # a ROOT bone's rotation is never applied (TexturedModel gives a parentless bone PartPose.offset(0, 0, 0))
    root = {"minecraft:geometry": [{"bones": [{"name": "root", "pivot": [0, 0, 0], "rotation": [0, 0, 90],
                                               "cubes": [{"origin": [0, 0, 0], "size": [1, 1, 16]}]}]}]}
    r2, top2 = A.model_extent(root)
    assert abs(r2 - math.hypot(1, 16)) < 1e-9 and abs(top2 - 1.0) < 1e-9


def _zip(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for n, d in files.items():
            z.writestr(n, json.dumps(d))


def test_species_size_applies_additions_and_a_datapack_overrides_a_mod(tmp_path):
    # Removing this lets an addition's hitbox be crossed with the base file's scale (Vikavolt 2.0 x 2.5 at 1.0
    # instead of 0.75), or a world datapack's species file be ignored for a mod's.
    _zip(tmp_path / "mods" / "a.jar", {
        "data/cobblemon/species/generation7/vikavolt.json": {"hitbox": {"width": 1, "height": 1}, "baseScale": 1},
        "data/cobblemon/species/generation1/onix.json": {"hitbox": {"width": 2, "height": 4}, "baseScale": 1},
        "data/cobblemon/species/generation9/pawmot.json": {}})
    _zip(tmp_path / "datapacks" / "b.zip", {
        "data/cobblemon/species_additions/vikavolt.json": {"target": "cobblemon:vikavolt",
                                                            "hitbox": {"width": 2.0, "height": 2.5},
                                                            "baseScale": 0.75},
        "data/cobblemon/species/generation1/onix.json": {"hitbox": {"width": 3, "height": 5}, "baseScale": 1}})
    arch = A.Archives(tmp_path)
    v = A.species_size(arch, "vikavolt")
    assert (v["width"], v["height"], v["scale"]) == (1.5, 1.875, 0.75)
    assert A.species_size(arch, "onix")["width"] == 3.0
    p = A.species_size(arch, "pawmot")
    assert (p["width"], p["height"]) == (1.0, 1.0)


def test_the_size_table_parser_reads_all_eight_rows():
    # Removing this lets the table comparison silently compare nothing when the table's format changes.
    t = A.doc_table()
    assert sorted(t) == A.GYMS
    assert t["gym1"]["radius"] == ("onix", 10.56)


def test_the_audit_shares_no_derivation_with_the_builder():
    # Removing this lets the audit drift into importing the builder's geometry or its size file, after which it can
    # only agree with it (CLAUDE.md, "How to prove an audit is independent").
    tree = ast.parse((ROOT / "tools" / "gym_arenas_audit.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    assert not names & {"gym_arenas", "pokemon_sizes", "gym_buildings", "gym_interiors"}
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and len(n.value) < 80]
    assert not [s for s in strings if "gym_arena_sizes.json" in s or s.endswith("survey.json")]


# ============================================================================================ the real arenas
@pytest.fixture(scope="module")
def packs(tmp_path_factory):
    """The arenas and the buildings built into a temporary directory, the dig (tools/gym_interiors.py writes only to
    build/) where its tool puts it; and the ground."""
    try:
        import ground
        G = ground.load()
    except (SystemExit, OSError) as e:   # terrain.py exits on an unset source root; a missing file is an OSError
        pytest.skip("no canonical heightmap here: %s" % e)
    if not (A.SNAPSHOT / "mods").exists():
        pytest.skip("no server snapshot with the jars at %s" % A.SNAPSHOT)
    out = tmp_path_factory.mktemp("arena_audit")
    arenas, buildings = out / "arenas", out / "buildings"
    for cmd in ([sys.executable, str(ROOT / "tools" / "gym_arenas.py"), "build", "--out", str(arenas)],
                [sys.executable, str(ROOT / "tools" / "gym_buildings.py"), "build", "--out", str(buildings)],
                [sys.executable, str(ROOT / "tools" / "gym_interiors.py"), "build"]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, "%s failed: %s" % (cmd[1], (r.stderr or r.stdout)[-800:])
    return G, arenas, buildings


@pytest.fixture(scope="module")
def real(packs):
    """Every gym audited from the functions built in `packs`."""
    G, arenas, buildings = packs
    arch = A.Archives()
    sizes = A.compare_sizes(arch, A.GYMS)
    res = {}
    for g in A.GYMS:
        f = A.audit_gym(g, arenas, G, arch, sizes[g]["size"], hosts=(buildings, None))
        f["size_vs_doc"] = sizes[g]["diffs"]
        res[g] = f
    return res


def kinds(f, *prefixes):
    return [p for p in f["problems"] if p.startswith(prefixes)]


def gyms_except(marks):
    return [pytest.param(g, marks=marks[g]) if g in marks else g for g in A.GYMS]


# was the gym7 adit finding (fixed 2026-10-09); kept as the record of what was found
ADIT_FIXED = (
    "FINDING gym7: lanterns hung in the adit's third headroom course, (6179,104,5006), (6179,100,5010), "
    "(6175,95,5012), (6171,91,5012), stop an upright player on the flight (head 1.8 over a tread's low half meets the "
    "lantern 1/16 lower); only crouching passes, both ways (build/.../gym7.mcfunction 'lanterns hung from the adit's "
    "roof')")


# FIXED 2026-10-09 by the main session (gym7 adit lanterns moved into the walls): its strict xfail turned red, as written, and was removed
@pytest.mark.parametrize("gym", A.GYMS)
def test_reach_down_to_the_challenger_and_back_up(real, gym):
    # Removing this lets an arena be built that a player cannot reach on foot, or cannot leave: a softlock.
    f = real[gym]
    assert not kinds(f, "REACH"), kinds(f, "REACH")
    assert f["reach_down"] and f["reach_up"]


def test_gym2_ledger_gallery_reaches_the_slipway_through_its_door_and_only_through_it(packs):
    # Removing this loses the one proof gym 2's builder said its own check could not give: that the puzzle route's
    # last room (the ledger gallery, data/gym_interiors.json gym2 route) leads to the arena and back. The second half
    # walls the door to show the proof rests on the door and not on a path the model invented.
    G, arenas, buildings = packs
    w, s, bounds, through, _aw, _hc, _logs = A.assemble("gym2", arenas, G, hosts=(buildings, None))
    region = [bounds, s["host_box"]] + through
    box = (min(b[0] for b in region) - 2, min(b[1] for b in region) - 3, min(b[2] for b in region) - 2,
           max(b[3] for b in region) + 2, max(b[4] for b in region) + 3, max(b[5] for b in region) + 2)
    ps = A.markers(w, bounds)["player_stand_position"][0]
    stand = (ps[0], ps[2], ps[1] + A.spawn_height_offset())
    walker = A.Walker(w, box)
    start = walker.settle(*s["route_end"])
    assert s["route_end"] == (1603, 99, 2874)
    assert stand in walker.reach(start) and start in walker.reach(stand)
    for y in (99, 100):
        assert A.name_of(w.get(1606, y, 2877)) == "minecraft:dark_oak_door"
        w.set((1606, y, 2877), "minecraft:stone", "test")
    walled = A.Walker(w, box)
    assert stand not in walled.reach(start) and start not in walled.reach(stand)


# FIXED 2026-10-09 by the main session (gym7 adit lanterns moved into the walls): its strict xfail turned red, as written, and was removed
@pytest.mark.parametrize("gym", A.GYMS)
def test_the_arena_descent_is_climbed_without_a_jump(real, gym):
    # Removing this lets a stair the generator promises to be walkable both ways need a jump (the 'tread_dropped'
    # mutation), which is invisible to a walk that may jump.
    f = real[gym]
    assert not kinds(f, "STAIR"), kinds(f, "STAIR")
    assert f.get("host_floor_without_jump", 0) > 0


@pytest.mark.parametrize("gym", A.GYMS)
def test_clearance_round_both_pokemon_blocks_at_the_measured_size(real, gym):
    # Removing this lets a wall stand inside the circle the largest Pokemon on the leader's team sweeps.
    f = real[gym]
    assert not kinds(f, "CLEARANCE"), kinds(f, "CLEARANCE")
    assert f["trainer_pokemon_clear_slack"] is None or f["trainer_pokemon_clear_slack"] >= 0


# FIXED 2026-10-09 by the main session (gym7 adit walls and ceiling written): its strict xfail turned red, as written, and was removed
@pytest.mark.parametrize("gym", A.GYMS)
def test_shell_bounds_and_seat_move(real, gym):
    # Removing this lets a cave open into an arena, a write land outside its declared boxes, or the seat move leave
    # the leader in the hall (all three are the same replay).
    f = real[gym]
    assert not kinds(f, "SHELL", "BOUNDS", "marker", "leader spawner", "the hall spawner"), f["problems"]


@pytest.mark.parametrize("gym", A.GYMS)
def test_cover_over_the_arena(real, gym):
    # Removing this lets an arena's top stand at or above the ground in the worst case of the heightmap's rounding.
    f = real[gym]
    assert not kinds(f, "COVER"), kinds(f, "COVER")
    assert f["cover_min"] >= 1


@pytest.mark.parametrize("gym", A.GYMS)
def test_no_water_or_lava_gets_in_and_no_hazard_on_the_walk(real, gym):
    # Removing this lets gym 2's lake or channel, or gym 7's lava, reach a cell a player walks.
    f = real[gym]
    assert not kinds(f, "WATER", "LAVA", "HAZARD"), kinds(f, "WATER", "LAVA", "HAZARD")


# FIXED 2026-10-09 by the main session (gym1 landings lit from the stair wall): its strict xfail turned red, as written, and was removed
@pytest.mark.parametrize("gym", A.GYMS)
def test_no_walkable_arena_cell_at_block_light_zero(real, gym):
    # Removing this lets a monster spawn inside an arena or on its descent.
    f = real[gym]
    assert not kinds(f, "LIGHT"), kinds(f, "LIGHT")


SIZE_TABLE = {
    "gym1": "radius: onix 10.50 measured, 10.56 in the table (the table keeps the root bone's pivot, which "
            "TexturedModel subtracts)",
    "gym2": "height: floatzel's model top 1.72 measured, the table's floatzel 1.53",
    "gym3": "height: electabuzz 1.93 measured, 1.96 in the table",
    "gym4": "height: cradily's model top 3.25 measured, the table's tangrowth 2.72 (bone rotation sign)",
    "gym6": "radius exeggutor 2.51 measured vs slowbro 2.09; height exeggutor 3.53 vs hatterene 6.13 (the table turns "
            "Hatterene's hat arm up; TexturedModel turns it down)",
    "gym8": "height: rhyperior 3.61 measured, 3.78 in the table",
}


@pytest.mark.parametrize("gym", gyms_except({g: pytest.mark.xfail(strict=True, reason="FINDING " + r)
                                             for g, r in SIZE_TABLE.items()}))
def test_the_size_table_agrees_with_the_jars(real, gym):
    # Removing this lets docs/world-building/GYM_ARENAS.md's size table drift from the jars it was measured from.
    assert real[gym]["size_vs_doc"] == []
