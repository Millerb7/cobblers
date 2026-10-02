"""tools/sea_life_audit.py: the independent audit of the shore, the wrecks and Rift debris and the two sea caves
(cobblers_sea_life).

The synthetic half builds a sea whose numbers are computable by hand (sea level y62; seabed y30 west of x50 and y20
for z >= 100; land at y70 east of x50, or as a test sets it) and hand-written commands, and proves each check fires
on its fault and stays quiet on the correct case. The surfacing-cave fixture is one straight passage at y57 from a
mouth at x50 to a riser at x60, a pool at y62 and a 3-wide chamber over it: its underwater length is
5 (surface to mouth) + (9 + sqrt 2 + 4) / ratio, by hand. The real half (marked slow) runs the audit on the pack
tools/sea_life.py built; it skips when the pack or the heightmap is absent. Known faults in that pack are xfail(strict).

What none of this covers: coral, kelp and seagrass living there in game (P6), an air chamber staying dry (P1), the
swim itself (the 5 blocks a second is EXP-042's, relayed through data/ferries.json), and gate lines the data does not
state as points (sea_life_audit.gate_lines() models the rest its own way and says so).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sea_life_audit as SA        # noqa: E402
import water_life_replay as R      # noqa: E402

SEA = 62


class FakeGround:
    def __init__(self, land=70):
        self.land = land

    def __call__(self, x, z):
        if x >= 50:
            return self.land
        return 20 if z >= 100 else 30

    def box(self, x0, z0, x1, z1):
        return np.array([[self(x, z) for x in range(x0, x1 + 1)] for z in range(z0, z1 + 1)])


SPEC = {
    "shore": {"kelp": {"max_top_below_surface": 2},
              "sea_cave": {"coast_box": "box", "shell": 4, "export_tolerance": 1,
                           "descent": {"water_clearance": 2}}},
    "finds": {"bands": {"surf": {"depth": [6, 35]}, "dive": {"depth": [36, 60]}}, "total": [2, 3],
              "surf_share": [0.0, 1.0], "cache_share": [0.0, 1.0], "debris_line_spacing_blocks": [40, 64],
              "debris_line_jitter_blocks": 4},
    "surfacing_cave": {"mouth": [50, 0], "tube": {"r": 0, "height": 1}, "pool_level": 62,
                       "chamber": {"centre": [60, 0], "half_x": 1, "half_z": 1, "height": 2}, "shell": 4,
                       "export_tolerance": 1, "natural_seabed": 1, "max_mouth_cells": 16},
}
SHAPE = {"coasts": {"flats": [{"box": [0, 0, 20, 20]}], "gate_line_clearance_blocks": 10,
                    "skerries": [{"id": "box", "box": [0, 0, 1, 1]}],
                    "relic_reef": {"centre": [0, 0], "outer_radius": [10, 20], "drop_width_blocks": 2,
                                   "sector_bearing_deg": [0, 359], "sector_fade_deg": 0, "min_depth": 3}}}


def ctx(land=70, speed=1.0, gates=()):
    t = R.Terrain(FakeGround(land), SEA, {})
    blackout = {"water": {"surf_bonus_ticks": 0, "pulse_ticks": 0}}
    return SA.Ctx(t, SPEC, SHAPE, blackout, speed, gate_lines=gates)


def world(c, lines, group="3build_0_0"):
    W = R.World(c.t)
    R.replay(W, [(group, [R.parse_line(l) for l in lines])])
    return W


def problems():
    return {k: [] for k in SA.CHECKS}


# ------------------------------------------------------------------------------------------------------ flora


def test_a_kelp_top_two_under_the_sea_surface_is_reported_and_three_under_is_not():
    # Without it, sea kelp could stand within 2 of the surface (WATER_LIFE 3: "never within 2 of the surface").
    c = ctx()
    for top, bad in ((60, True), (59, False)):
        W = world(c, ["fill 10 31 0 10 %d 0 minecraft:kelp_plant" % (top - 1),
                      "setblock 10 %d 0 minecraft:kelp[age=25]" % top], "4flora_0_0")
        P = problems()
        SA.check_flora(c, W, P, set())
        assert any("within 2 of the surface" in p for p in P["flora"]) is bad


def test_seagrass_off_the_flats_fails():
    # Without it, seagrass could be laid on rock coasts the spec gives kelp only (WATER_LIFE 3).
    c = ctx()
    W = world(c, ["setblock 30 31 30 minecraft:seagrass"], "4flora_0_0")
    P = problems()
    SA.check_flora(c, W, P, set())
    assert any("outside every flats box" in p for p in P["flora"])


def test_coral_beyond_the_reef_and_coral_with_no_water_fail():
    # Without it, coral could spill past the reef platform, or a coral block be sealed in and die (WATER_LIFE 3).
    c = ctx()
    W = world(c, ["setblock 30 31 0 minecraft:brain_coral_block",
                  "setblock 5 31 5 minecraft:tube_coral_block",
                  "setblock 4 31 5 minecraft:stone", "setblock 6 31 5 minecraft:stone",
                  "setblock 5 31 4 minecraft:stone", "setblock 5 31 6 minecraft:stone",
                  "setblock 5 32 5 minecraft:stone"], "4flora_0_0")
    P = problems()
    res = SA.check_coral(c, W, P)
    text = " ".join(P["coral"])
    assert "beyond the reef's outermost radius 22" in text and "no water on any face" in text
    assert res["beyond_radius"]["r"] == [30.0, 30.0]


# ------------------------------------------------------------------------------------------------------ finds


def test_finds_are_counted_by_band_and_an_unseated_one_fails():
    # Without it, counts per band would be read from the plan, not measured, and a floating wreck would pass.
    c = ctx()
    W = world(c, ["fill 10 31 0 12 31 0 minecraft:spruce_planks",
                  "setblock 11 32 0 minecraft:lantern[hanging=false,waterlogged=true]",   # the Surf find's hook
                  "fill 10 25 150 12 25 150 minecraft:spruce_planks"])                    # 4 over its ground
    P = problems()
    res = SA.check_finds(c, W, P, [], set())
    assert (res["finds"], res["surf"], res["dive"]) == (2, 1, 1)
    assert res["depths"] == [32, 42]
    assert len([p for p in P["finds"] if "not seated" in p]) == 1 and "(10, 25, 150)" in P["finds"][0]


def test_a_find_near_the_surface_inside_a_gate_clearance_fails():
    # Without it, a wreck could become a rest point on a crossing declared a gate (coasts.gate_line_clearance_blocks).
    c = ctx(gates=[("g", (10, -20), (10, 20))])
    gate_ix, missing = SA.gate_index(c)
    assert not missing and (10, 0) in gate_ix and (21, 0) not in gate_ix
    W = world(c, ["fill 10 31 0 10 60 0 minecraft:spruce_log[axis=y]", "fill 9 31 0 11 31 0 minecraft:oak_planks"])
    P = problems()
    SA.check_finds(c, W, P, [], gate_ix)
    assert any("within 2 of the surface, inside a gate's clearance" in p for p in P["finds"])


def test_a_surf_find_with_no_light_and_no_mast_fails():
    # Without it, a Surf-reach find could carry no hook seen from above (data finds.hooks).
    c = ctx()
    W = world(c, ["fill 10 31 0 12 31 0 minecraft:spruce_planks", "fill 10 25 150 12 25 150 minecraft:oak_planks"])
    P = problems()
    SA.check_finds(c, W, P, [], set())
    assert any("no light and no mast" in p for p in P["finds"])


def test_a_door_a_bed_or_a_fence_gate_under_the_sea_is_a_breathing_pocket():
    # Without it, a wreck's door would give a diver a free breath, the bypass WATER_LIFE's Departures forbid.
    c = ctx()
    W = world(c, ["setblock 10 31 0 minecraft:oak_door[half=lower]",
                  "setblock 12 31 0 minecraft:spruce_slab[type=bottom,waterlogged=true]",
                  "setblock 14 30 0 minecraft:red_bed[part=foot]"])          # set into the bed, water above it
    P = problems()
    res = SA.check_flooded(c, W, P, set())
    assert res["dry_cells"] == 2
    assert {p.split()[1] for p in P["flooded"]} == {"minecraft:oak_door", "minecraft:red_bed"}


# -------------------------------------------------------------------------------------------- surfacing cave

CAVE = ["fill 50 57 0 59 57 0 minecraft:water",          # the passage
        "fill 60 57 0 60 62 0 minecraft:water",          # the riser up to the pool's surface at y62
        "fill 59 63 0 61 64 0 minecraft:air",            # the chamber over the pool
        "setblock 61 63 1 minecraft:barrel[facing=up]"]


def surfacing(lines, land=70, speed=1.0):
    c = ctx(land=land, speed=speed)
    W = world(c, lines, "2carve_0_0")
    caves = [set(x) for x in SA.components(SA.opened_cells(c, W))]
    P = problems()
    res = SA.check_surfacing(c, W, P, caves, None)
    return res, P["surfacing"]


def test_the_surfacing_path_lower_bound_is_the_hand_computed_one():
    # Without it, the air rule would rest on a number nobody can reproduce.
    res, P = surfacing(CAVE)
    ratio = R.octile3_worst_ratio()
    assert res["underwater_path_lower_bound"] == round(5 + (9 + math.sqrt(2) + 4) / ratio, 1)
    assert res["surf_air_blocks"] == 15.0                       # (0 + 300 + 0) ticks / 20 x 1 block a second
    assert not any("not longer than a Surf" in p for p in P)


def test_a_passage_a_surf_player_can_swim_fails_the_air_rule():
    # Without it, the surfacing cave could be reached on Surf's air alone, and Dive would gate nothing.
    res, P = surfacing(CAVE, speed=2.0)                         # 30 blocks of air: longer than the path
    assert any("not longer than a Surf player's 30.0" in p for p in P)


def test_the_pool_floor_and_mouth_of_a_correct_cave():
    # Without it, a cave whose pool is not flat, or whose floor cannot be walked from the pool, could pass.
    res, P = surfacing(CAVE)
    assert res["pool_surface_ys"] == [62] and res["floor_reached"] == res["floor_cells"] == 2
    assert res["water_breach_cells"] == 1 and res["air_breach_cells"] == 0
    assert any("not within WATER_LIFE 5's 20-40" in p for p in P)      # this mouth is 5 deep, on purpose


def test_a_thin_roof_over_the_chamber_fails_the_shell():
    # Without it, the chamber could sit a block or two under the ground (WATER_BUILD_PLAN 6.4: shell at least 4).
    _res, P = surfacing(CAVE, land=66)
    assert any("under 4 blocks of rock" in p for p in P)
    _res, P = surfacing(CAVE, land=70)
    assert not any("blocks of rock" in p for p in P)


def test_water_beside_air_is_not_a_flat_pool():
    # Without it, a chamber whose water would flow into its air pocket would pass.
    _res, P = surfacing(CAVE + ["setblock 61 63 0 minecraft:water"])
    assert any("the water flows" in p for p in P) and any("not one flat pool" in p for p in P)


def test_a_floor_out_of_reach_of_the_pool_is_a_trap():
    # Without it, a gallery a player can fall into or never reach would pass (VR caves' walk-out rule).
    _res, P = surfacing(CAVE + ["fill 61 65 0 61 68 0 minecraft:air", "fill 62 67 0 62 68 0 minecraft:air"], land=80)
    assert any("not reachable on foot from the pool" in p for p in P)


def test_a_cave_open_to_the_air_fails():
    # Without it, the sealed view could be a hole a player climbs out of (or rain falls into).
    _res, P = surfacing(CAVE + ["fill 59 65 0 59 70 0 minecraft:air"])
    assert any("touch open air" in p for p in P)


# ------------------------------------------------------------------------------------------------- machinery


def test_the_octile_ratio_bounds_every_direction():
    # Without it, the swim length's lower bound could be above the true length and pass a too-short passage.
    r = R.octile3_worst_ratio()
    assert 1.0824 < r < math.sqrt(3)
    rng = np.random.default_rng(7)
    for v in rng.random((200, 3)):
        a, b, c = sorted(v, reverse=True)
        cost = math.sqrt(3) * c + math.sqrt(2) * (b - c) + (a - b)
        assert cost / math.sqrt(a * a + b * b + c * c) <= r + 1e-3


def test_walking_needs_a_floor_and_at_most_one_block_of_climb():
    # Without it, the walk-out check would let a player climb a two-block step.
    c = ctx(land=80)
    W = world(c, ["fill 60 81 0 70 82 0 minecraft:air", "fill 60 81 0 64 81 0 minecraft:stone",
                  "fill 60 83 0 64 83 0 minecraft:air", "fill 65 82 0 70 83 0 minecraft:air"])
    # floor at y80 for x65-70 (feet y81); a raised floor at y81 for x60-64 (feet y82): one block up, walkable
    corridor = lambda q: 60 <= q[0] <= 70 and q[2] == 0 and 80 < q[1] < 86        # noqa: E731
    reach = SA.walk(W, {(70, 81, 0)}, corridor)
    assert (60, 82, 0) in reach
    W2 = world(c, ["fill 60 81 0 70 84 0 minecraft:air", "fill 60 81 0 64 82 0 minecraft:stone"])
    reach = SA.walk(W2, {(70, 81, 0)}, corridor)
    assert (65, 81, 0) in reach and (60, 83, 0) not in reach


def test_a_cache_with_no_record_or_with_a_trigger_elsewhere_fails():
    # Without it, a barrel could be scenery with no reward behind it.
    c = ctx()
    W = world(c, ["setblock 10 31 0 minecraft:barrel[facing=up]"])
    P = problems()
    SA.check_cache(c, W, P, [])
    assert any("no data/rewards.json record" in p for p in P["cache"])
    c.rewards = [{"id": "sea_life_x", "container": {"at": [10, 31, 0]},
                  "trigger": {"min": [20, 31, 0], "max": [22, 33, 2]}, "contents": []}]
    P = problems()
    SA.check_cache(c, W, P, [])
    assert any("does not hold its barrel" in p for p in P["cache"])


# ------------------------------------------------------------------------------------- the pack as built


@pytest.fixture(scope="module")
def real():
    from terrain import TerrainUnavailable
    if not SA.PACK.joinpath(*SA.FN).joinpath("index.txt").is_file():
        pytest.skip("build/datapacks/cobblers_sea_life is not built here (python tools/sea_life.py build)")
    try:
        c = SA.load_ctx()
    except (TerrainUnavailable, OSError) as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])
    return SA.audit(c)


KNOWN = {
    "flora": "sea kelp tops stand at sea - 2 (13,585 of them on 2026-10-02): data/sea_life.json shore.kelp."
             "max_top_below_surface 2, applied at tools/sea_life.py:1487, against WATER_LIFE 3's 'never within 2 of "
             "the surface' (the lake pack reads the same sentence as level - 3)",
    "coral": "1,294 coral writes 101-107 from the reef's centre, past outer_radius max + drop_width_blocks: "
             "tools/sea_life.py:1522 takes water_shape.reef_footprint, the flats pass's keep-out mask with a +6 margin "
             "(tools/water_shape.py:2181), as the reef's extent",
    "flooded": "4 oak doors, 4 red beds and 2 fence gates under the sea in the house and garden-gate debris "
               "(tools/sea_life.py:279-282, 314): none is waterloggable, so each cell is a dry pocket a diver breathes "
               "in; tools/sea_life.py:81 and 1707 exempt them from the builder's own flooded check",
    "light": "23 roofed floor cells of the waterline sea cave at block light 0 (e.g. 391, 59, 3502): hostiles spawn "
             "in an S0 cave beside the beach",
}
REAL_CHECKS = ["parse", "flora", "coral", "finds", "flooded", "cut", "clear", "surfacing", "seacave", "light",
               "cache", "blocks", "foreign", "limits"]


@pytest.mark.slow
@pytest.mark.parametrize("check", [pytest.param(k, marks=pytest.mark.xfail(strict=True, reason=KNOWN[k]))
                                   if k in KNOWN else k for k in REAL_CHECKS])
def test_the_built_sea_pack_passes(real, check):
    # Without it, a regression in tools/sea_life.py or its data would reach a world with only its own checks run.
    assert real["problems"][check] == []


@pytest.mark.slow
def test_the_built_surfacing_cave_is_dive_content_by_air(real):
    # Without it, the Windward Sink's only gate (its length) could be lost and the audit not say how much is left.
    s = real["surfacing"]
    assert s["underwater_path_lower_bound"] > s["surf_air_blocks"] and s["floor_reached"] == s["floor_cells"] > 0


@pytest.mark.slow
def test_the_built_finds_are_forty_to_sixty_with_a_quarter_in_surf_reach(real):
    # Without it, the find counts would only be the builder's own report (WATER_LIFE 4: 40-60, a quarter <= 35 deep).
    f = real["finds"]
    assert 40 <= f["finds"] <= 60 and 0.2 <= f["surf"] / float(f["finds"]) <= 0.32
