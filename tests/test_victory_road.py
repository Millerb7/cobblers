"""tools/victory_road.py and data/victory_road.json: the gauntlet out of the wound (schema 2).

One road, not a labyrinth: an authored spine from the Deep's floor at y0 through five domed caverns, up a
switchback stair and out onto the League's apron, with ten trainer stands, one rest station and light placed by
tier. What is asserted here is what would be expensive to discover in game -- the order the passes write in (a
cavern shell written after the corridor's air would seal the road), the shape of the authored spine, where the
ten stands and the rest station sit, where the road surfaces relative to the League's lot, and the block light
the plan leaves at a player's feet, since fightorflight reads 7 and 12 as its own cut-offs.

The light numbers come from the tool's own light_field, which replays the plan's commands and propagates light
six ways losing one per block. test_block_light_falls_one_per_block_and_stops_at_solid and
test_light_does_not_wrap_from_one_face_of_the_box_to_the_other check that model on synthetic plans, so the
real-road light assertions rest on something that was itself tested.

Walkability is asserted from the finished space, not from the route's recorded heights: the route is the spine's
own line, and where the stair's first treads rise through it the block a player stands on is a block or two over
that line. So the test asks for ground under every route block and for a standable surface whose height never
rises more than one block from one route block to the next.

Not covered, and it needs a boot or a functional test:
  - that the functions load and run in Minecraft at all (command limits, chunk loading, /fill block counts);
  - that the blocks the spec names exist in the installed mod set: the build here runs with no --server-dir, so
    every block resolves to the modded first choice and no fallback path is exercised;
  - that Minecraft's own light engine agrees with light_field, and that fightorflight then behaves as claimed;
  - that a player can actually walk the road: a standable column under every route block is not a walk, and only
    a walk or tools/victory_road.py verify against a built world proves the rest;
  - the backfill pass (schema 1's labyrinth being buried), the written .mcfunction files, and verify itself;
  - whether the caverns look like caves, and everything about pacing.
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import victory_road as VR  # noqa: E402

SPEC = json.loads((ROOT / "data" / "victory_road.json").read_text(encoding="utf-8"))
WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
REGIONS = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))
LEAGUE = json.loads((ROOT / "data" / "rift_league_tunnel.json").read_text(encoding="utf-8"))

AIR = "minecraft:air"


# ------------------------------------------------------------------ the built road, once

@pytest.fixture(scope="module")
def road():
    """(plan, spec) from one real build, or a skip.

    Module-scoped on purpose: the build reads the canonical heightmap and the owner's traced regions and takes
    seconds, and every plan assertion in this file shares the one result.
    """
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the road cannot be built from the canonical heightmap")
    hm = Path(root) / WORLD["heightmap"]["path"]
    ann = Path(root) / REGIONS["source"]["file"].split(" ")[0]
    if not (hm.is_file() and ann.is_file()):
        pytest.skip("the heightmap or the owner's annotated tracing is not under COBBLERS_SOURCE_ROOT")
    if hashlib.sha256(ann.read_bytes()).hexdigest() != REGIONS["source"]["sha256"]:
        pytest.skip("the annotated heightmap on disk is not the one data/rift_regions.json pins")
    try:
        return VR.build(root)
    except Exception as e:                        # an unusable or unpinned heightmap is a skip, not a failure
        if e.__class__.__name__ in ("TerrainUnavailable", "DeepError"):
            pytest.skip(str(e))
        raise


@pytest.fixture(scope="module")
def field(road):
    """(light, air, origin, light block) over the whole road, replayed from the plan's own commands."""
    plan, _spec = road
    return VR.light_field(plan)


@pytest.fixture(scope="module")
def report(road):
    plan, _spec = road
    return VR.light_report(plan)[0]


@pytest.fixture(scope="module")
def writes(road):
    """Per cell over the plan's box: the last index that wrote the corridor's wall block, and the first that
    cut air there. One replay, shared by the pass-order tests."""
    plan, spec = road
    lines = plan["lines"]
    wall = spec["corridor"]["wall"]
    xs, ys, zs = [], [], []
    for ln in lines:
        t = ln.split()
        if t[0] == "fill":
            xs += [int(t[1]), int(t[4])]
            ys += [int(t[2]), int(t[5])]
            zs += [int(t[3]), int(t[6])]
        else:
            xs.append(int(t[1]))
            ys.append(int(t[2]))
            zs.append(int(t[3]))
    X0, Y0, Z0 = min(xs), min(ys), min(zs)
    shape = (max(ys) - Y0 + 1, max(zs) - Z0 + 1, max(xs) - X0 + 1)
    last_wall = np.full(shape, -1, np.int32)
    first_air = np.full(shape, -1, np.int32)
    for i, ln in enumerate(lines):
        t = ln.split()
        if t[0] == "fill":
            a = (slice(int(t[2]) - Y0, int(t[5]) - Y0 + 1), slice(int(t[3]) - Z0, int(t[6]) - Z0 + 1),
                 slice(int(t[1]) - X0, int(t[4]) - X0 + 1))
            block = t[7]
        else:
            a = (int(t[2]) - Y0, int(t[3]) - Z0, int(t[1]) - X0)
            block = t[4]
        if block == wall:
            last_wall[a] = i
        elif block == AIR:
            cur = np.asarray(first_air[a])
            first_air[a] = np.where(cur < 0, i, cur)
    return last_wall, first_air


def _at(field, x, y, z):
    """(block light, is air) at one position of the finished space."""
    lit, air, (X0, Y0, Z0), _b = field
    return int(lit[y - Y0, z - Z0, x - X0]), bool(air[y - Y0, z - Z0, x - X0])


def _drop(field, x, y, z, limit=40):
    """Blocks of air between a route position's feet and the first solid block under it."""
    _lit, air, (X0, Y0, Z0), _b = field
    d = 0
    while d < limit and air[y - 1 - d - Y0, z - Z0, x - X0]:
        d += 1
    return d


def _surface(field, x, y, z, up=8, down=4):
    """The y a player stands on in this column, searched from the route's own height outwards, or None.

    Standing means two blocks of air with something solid under them. The route records the spine's line; where
    the stair's treads rise through it the ground is over that line, and where the road steps down it is under.
    """
    def ok(yy):
        return _at(field, x, yy, z)[1] and _at(field, x, yy + 1, z)[1] and not _at(field, x, yy - 1, z)[1]
    for d in range(0, up + 1):
        if ok(y + d):
            return y + d
    for d in range(1, down + 1):
        if ok(y - d):
            return y - d
    return None


# ------------------------------------------------------------------ the spec reads on its own

# removing this lets a chamber or the stair name a waypoint the spine does not have, which the build meets as a
# KeyError in the middle of a carve instead of as a readable spec error
def test_every_chamber_and_the_stair_stand_on_a_named_waypoint():
    named = [p["name"] for p in SPEC["spine"] if p.get("name")]
    assert len(set(named)) == len(named), "two waypoints share a name"
    for ch in SPEC["chambers"]:
        assert ch["at"] in named, ch["at"]
    assert SPEC["stair"]["at"] in named
    assert SPEC["spine"][0]["name"] == "deep_mouth", "the road no longer starts at the Deep's mouth"


# removing this lets the gauntlet quietly become nine fights or eleven: the count is the shape of the run, five
# before the rest station and five after, and the build refuses to lay out any other number
def test_the_gauntlet_is_ten_fights_around_one_rest_station():
    assert SPEC["trainers"]["count"] == 10
    rest = [c for c in SPEC["chambers"] if c.get("rest")]
    assert len(rest) == 1, "exactly one cavern carries the rest station"
    # one fight in the corridor before each cavern, one in each cavern that is not the rest, one at the stair
    assert len(SPEC["chambers"]) + (len(SPEC["chambers"]) - len(rest)) + 1 == SPEC["trainers"]["count"]
    assert len([c for c in SPEC["chambers"] if c["kind"] == "landmark"]) == 1


# removing this lets a spine leg densify into a route that teleports: the walk is what the stands, the light and
# the trainer index are all placed along, and a two-block jump in it is a jump in every one of them
def test_the_spine_densifies_to_single_block_steps():
    spine = [(p["x"], p["y"], p["z"]) for p in SPEC["spine"]]
    walk = VR.densify(spine)
    assert walk[0] == spine[0] and walk[-1] == tuple(spine[-1])
    worst = max(max(abs(b[i] - a[i]) for i in (0, 1, 2)) for a, b in zip(walk, walk[1:]))
    assert worst == 1, "the densified spine steps %d blocks somewhere" % worst
    assert len(walk) > 500, "the spine densified to only %d blocks" % len(walk)


# removing this lets a pair of waypoints climb steeper than a player can walk, which reads in game as a wall
# with a corridor behind it rather than as a road
def test_no_leg_of_the_spine_is_steeper_than_the_corridor_allows():
    spine = [(p["x"], p["y"], p["z"]) for p in SPEC["spine"]]
    mx = SPEC["corridor"]["max_grade"]
    steep = [(i, round(g, 3)) for i, g in VR.grades(spine) if g > mx]
    assert not steep, "legs steeper than %s: %s" % (mx, steep)


# removing this lets the road surface somewhere other than the League's apron; schema 2 exists because schema 1
# ended on a shelf short of the tower, and the lot box lives in data/rift_league_tunnel.json, not here
def test_the_spec_exit_lands_south_of_the_league_lot_inside_its_skirt():
    lot = LEAGUE["lot"]
    x0, _z0, x1, z1 = lot["box"]
    ex, ez = SPEC["exit"]["at"]
    assert SPEC["exit"]["lot_y"] == lot["y"], "the spec's idea of the lot's level is not the lot's level"
    assert SPEC["exit"]["y"] == lot["y"] + 1, "the exit is not the standing level over the lot's surface block"
    assert x0 <= ex <= x1, "the exit is not under the lot's x span"
    assert ez > z1, "the exit is not south of the lot's south edge"
    assert ez - z1 <= lot["skirt"], "the exit is %d south of the lot, past its %d skirt" % (ez - z1, lot["skirt"])
    assert SPEC["exit"]["ramp_from_z"] > ez, "the ramp opens north of the exit, so the last steps stay roofed"


# ------------------------------------------------------------------ the order of the passes

# removing this lets a cavern's shell be written after the corridor's air was cut: the shell would seal the
# corridor running into the cavern, and the road would be a dead end nobody finds until they walk it
def test_no_wall_is_written_after_the_first_air_is_cut(road):
    plan, spec = road
    lines = plan["lines"]
    wall = spec["corridor"]["wall"]
    first_air = next(i for i, ln in enumerate(lines) if ln.endswith(AIR))
    assert first_air > 0, "the plan cuts air before it builds anything"
    late = [(i, lines[i]) for i in range(first_air, len(lines)) if lines[i].endswith(wall)]
    assert not late, "%d wall writes come after air is cut, e.g. %s" % (len(late), late[:2])
    # later passes may write solid again -- the floor, the rest station, the stands, the light -- but never shell
    after = {ln.rsplit(" ", 1)[1] for ln in lines[first_air:] if not ln.endswith(AIR)}
    assert after and wall not in after, sorted(after)


# removing this lets the pass order break cell by cell rather than line by line: one shell block laid into a
# cell that was already cut open is what seals a corridor, and only a replay of the plan sees it
def test_no_cell_is_walled_after_it_was_cut_open(writes):
    last_wall, first_air = writes
    both = (last_wall >= 0) & (first_air >= 0)
    n = int(both.sum())
    assert n > 10000, "only %d cells were both walled and cut: the plan does not exercise the order" % n
    bad = int((first_air[both] <= last_wall[both]).sum())
    assert bad == 0, "%d of %d shared cells were walled after being cut open" % (bad, n)


# ------------------------------------------------------------------ the ten fights and the rest station

# removing this lets a stand drift off the walked route, double up inside the rest station, or stand within
# earshot of the next one: the distance between fights is the pacing of the gauntlet
def test_the_ten_stands_are_on_the_route_outside_the_rest_and_min_apart(road):
    plan, spec = road
    stands = [tuple(p) for p in plan["stands"]]
    route = {tuple(p) for p in plan["route"]}
    assert len(stands) == spec["trainers"]["count"] == 10
    assert len(set(stands)) == len(stands), "two stands share a position"
    off = [s for s in stands if s not in route]
    assert not off, "stands that are not on the walked route: %s" % off
    rb = plan["rest"]
    inside = [s for s in stands if rb[0] <= s[0] <= rb[3] and rb[2] <= s[2] <= rb[5]]
    assert not inside, "stands inside the rest station: %s" % inside
    apart = spec["trainers"]["min_apart"]
    worst = min(math.dist((a[0], a[2]), (b[0], b[2])) for a, b in zip(stands, stands[1:]))
    assert worst >= apart, "two consecutive stands are %.1f apart, under the %d minimum" % (worst, apart)


# removing this lets the rest station be built outside the cavern that is supposed to hold it, where its walls
# would be carved into rock, or lose a doorway and become a sealed box in the middle of the road
def test_the_rest_station_stands_in_the_rest_cavern_with_a_doorway_on_each_face(road, field):
    plan, spec = road
    name = next(c["at"] for c in spec["chambers"] if c.get("rest"))
    cx, cy, cz, R = plan["chambers"][name]
    x0, y0, z0, x1, _y1, z1 = plan["rest"]
    assert y0 == cy, "the rest station's floor is not the cavern's floor"
    for X in (x0, x1):
        for Z in (z0, z1):
            assert math.hypot(X - cx, Z - cz) < R, "a corner of the rest station is outside %s" % name
    wx, wz = spec["rest"]["size"]
    assert (x1 - x0, z1 - z0) == (wx - 1, wz - 1), "the rest station is not the size the spec gives"
    for gz in (z0, z1):                                # a doorway through each face the road runs through
        open_at = [x for x in range(x0, x1 + 1) if _at(field, x, cy + 1, gz)[1]]
        assert open_at, "the face at z%d has no doorway" % gz
        assert len(open_at) <= 5, "the face at z%d is a gap, not a doorway: %s" % (gz, open_at)
        for x in open_at:                              # and the doorway is full height, not a slot
            assert all(_at(field, x, cy + dy, gz)[1] for dy in (0, 1, 2)), (gz, x)


# removing this lets the built exit drift off the spec's own coordinate; the spec is where the road is read, and
# a build that surfaces somewhere else makes the file fiction
def test_the_built_exit_is_the_spec_exit_and_open_where_it_surfaces(road, field):
    plan, spec = road
    ex, ey, ez = plan["exit"]
    assert [ex, ez] == spec["exit"]["at"] and ey == spec["exit"]["y"]
    assert ey == LEAGUE["lot"]["y"] + 1
    assert 0 < ez - LEAGUE["lot"]["box"][3] <= LEAGUE["lot"]["skirt"]
    assert _at(field, ex, ey, ez)[1] and _at(field, ex, ey + 1, ez)[1], "the exit is not open where it surfaces"
    assert not _at(field, ex, ey - 1, ez)[1], "there is nothing under the exit to stand on"


# ------------------------------------------------------------------ light as a difficulty setting

# removing this lets a fight start in the dark, where fightorflight makes Dark and Ghost types aggressive; the
# spec puts a light pool at every stand precisely so the ten fights are the calm ground on the road.
# Distance is measured in three dimensions, not the tool's horizontal hypot: the switchback stair folds the
# route over itself, so a horizontal radius of 6 around the tenth stand also catches stair legs 25 blocks below
# it, which are dark on purpose.
def test_no_route_block_near_a_trainer_stand_is_hostile_light(road, field):
    plan, _spec = road
    route = [tuple(p) for p in plan["route"]]
    worst = []
    for s in map(tuple, plan["stands"]):
        near = [p for p in route if math.dist(p, s) <= 6]
        assert len(near) >= 8, "only %d route blocks within 6 of the stand at %s" % (len(near), s)
        worst += [(p, _at(field, *p)[0]) for p in near if _at(field, *p)[0] <= 7]
    assert not worst, "%d route blocks within 6 of a stand are at or below light 7, e.g. %s" % (
        len(worst), worst[:3])


# removing this lets the corridors be lit like the caverns, and the dark between fights -- the whole difficulty
# claim of the tier table -- stops existing
def test_the_corridors_between_the_caverns_are_mostly_dark(report):
    cor = report["the corridors between"]
    assert cor["n"] > 200, "only %d corridor blocks sampled" % cor["n"]
    assert cor["hostile"] * 2 > cor["n"], "only %d of %d corridor blocks are at or below light 7" % (
        cor["hostile"], cor["n"])
    assert cor["median"] <= 7
    assert report["inside the caverns"]["median"] > cor["median"], \
        "the caverns are no brighter than the corridors between them"


# removing this lets the one safe room on the road become ground where Dark and Ghost types turn aggressive,
# which is the opposite of what a rest station is for
def test_no_part_of_the_rest_station_floor_is_hostile_light(road, field):
    plan, _spec = road
    x0, y0, z0, x1, _y1, z1 = plan["rest"]
    vals = [_at(field, x, y0, z)[0] for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)]
    assert len(vals) >= 100, "only %d floor cells sampled" % len(vals)
    assert min(vals) > 7, "the rest station's floor drops to light %d" % min(vals)


# removing this lets the rest station stop being calm everywhere it says it is. It failed until 2026-09-23,
# when the light lattice was anchored to the room instead of the world grid and the marker block stopped eating
# one of the lights: before that the low-x and low-z edges sat 2 blocks from the nearest light and read 10-11.
def test_the_rest_station_floor_is_calm_everywhere(road, field):
    plan, _spec = road
    x0, y0, z0, x1, _y1, z1 = plan["rest"]
    vals = [_at(field, x, y0, z)[0] for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)]
    assert min(vals) >= 12, "%d of %d rest floor cells are under light 12" % (sum(v < 12 for v in vals), len(vals))


# removing this lets the road hang over its own void again: until 2026-09-23 the corridor floor was laid with
# the walls and then cut away by the air pass wherever the road climbed, leaving 195 of 646 route blocks over
# air and up to 35 under the exit ramp. Nothing about a gauntlet survives a road with no floor.
def test_every_block_of_the_route_has_ground_directly_under_it(road, field):
    plan, _spec = road
    route = [tuple(p) for p in plan["route"]]
    assert len(route) > 600, "only %d route blocks: the road is not the whole road" % len(route)
    hanging = [(p, _drop(field, *p)) for p in route if _drop(field, *p) > 0]
    assert not hanging, "%d of %d route blocks hang over air, e.g. %s" % (len(hanging), len(route), hanging[:4])


# removing this lets the road stop being walkable without anything else noticing: a light block in the walking
# cell, a tread at head height at a switchback turn, or a step the player cannot climb. Measured on the
# finished space, not on the route's recorded heights, because where the stair's first treads rise through the
# spine's straight line at x3652-3653 z2522-2526 the ground really is a block or two over the route -- that is
# a step up onto the stair, and the one-block rule is what tells a step from a wall.
def test_the_route_is_walkable_end_to_end_stepping_up_no_more_than_one(road, field):
    plan, spec = road
    route = [tuple(p) for p in plan["route"]]
    sx, _sy, sz = next((p["x"], p["y"], p["z"]) for p in spec["spine"] if p.get("name") == spec["stair"]["at"])
    hw, hl = spec["stair"]["hall"]
    surf = [(p, _surface(field, *p)) for p in route]
    nowhere = [p for p, s in surf if s is None]
    assert not nowhere, "%d route blocks have nowhere to stand within 8 over or 4 under them: %s" % (
        len(nowhere), nowhere[:4])
    ys = [s for _p, s in surf]
    climbs = [(p, b - a) for (p, a), b in zip(surf, ys[1:]) if b - a > 1]
    assert not climbs, "the walking surface rises more than a block in one step at %s" % (climbs[:4],)
    falls = [(p, b - a) for (p, a), b in zip(surf, ys[1:]) if b - a < -3]
    assert not falls, "the walking surface drops far enough to hurt at %s" % (falls[:4],)
    # and the ground is only ever over the route where the stair rises through it, never elsewhere
    over = [(p, s) for p, s in surf if s > p[1]]
    hall = [p for p, _s in over
            if abs(p[0] - sx) <= hw // 2 and abs(p[2] - sz) <= hl // 2]
    assert len(hall) == len(over), "the ground stands over the route outside the stair hall: %s" % (
        [o for o in over if o[0] not in hall][:4],)
    assert len(over) <= 8, "%d route blocks are under their own ground, not the 5 the stair explains: %s" % (
        len(over), over)


# ------------------------------------------------------------------ the light model itself, on synthetic plans

# removing this lets light_field's propagation drift -- a wrong falloff, or light passing through stone -- while
# every light assertion above keeps reporting numbers that look plausible
def test_block_light_falls_one_per_block_and_stops_at_solid():
    plan = {"lines": ["fill 0 0 0 10 3 3 minecraft:stone",
                      "fill 0 1 1 10 1 1 minecraft:air",
                      "setblock 6 1 1 minecraft:stone",
                      "setblock 0 1 1 minecraft:pearlescent_froglight"]}
    lit, air, (X0, Y0, Z0), block = VR.light_field(plan)
    assert block == "minecraft:pearlescent_froglight"
    got = [int(lit[1 - Y0, 1 - Z0, x - X0]) for x in range(0, 11)]
    assert got[:6] == [15, 14, 13, 12, 11, 10], got
    assert got[6:] == [0, 0, 0, 0, 0], "light crossed the solid block at x6: %s" % got
    assert not air[1 - Y0, 1 - Z0, 6 - X0] and air[1 - Y0, 1 - Z0, 5 - X0]
    assert int(lit[0 - Y0, 1 - Z0, 1 - X0]) == 0, "light lit the stone floor under the tube"


# removing this lets the propagation use np.roll again: light would leave one face of the box and arrive at the
# other, and a dark corridor would read as lit because of a lamp on the far side of the plan
def test_light_does_not_wrap_from_one_face_of_the_box_to_the_other():
    along_x = {"lines": ["fill 0 0 0 10 3 3 minecraft:stone",
                         "fill 0 1 1 10 1 1 minecraft:air",
                         "setblock 0 1 1 minecraft:pearlescent_froglight"]}
    lit, _air, (X0, Y0, Z0), _b = VR.light_field(along_x)
    assert int(lit[1 - Y0, 1 - Z0, 10 - X0]) == 5, "the far x face is not 15 minus its distance"
    along_y = {"lines": ["fill 0 0 0 3 10 3 minecraft:stone",
                         "fill 1 0 1 1 10 1 minecraft:air",
                         "setblock 1 0 1 minecraft:pearlescent_froglight"]}
    lit, _air, (X0, Y0, Z0), _b = VR.light_field(along_y)
    assert int(lit[10 - Y0, 1 - Z0, 1 - X0]) == 5, "the far y face is not 15 minus its distance"
    along_z = {"lines": ["fill 0 0 0 3 3 10 minecraft:stone",
                         "fill 1 1 0 1 1 10 minecraft:air",
                         "setblock 1 1 0 minecraft:pearlescent_froglight"]}
    lit, _air, (X0, Y0, Z0), _b = VR.light_field(along_z)
    assert int(lit[1 - Y0, 10 - Z0, 1 - X0]) == 5, "the far z face is not 15 minus its distance"
