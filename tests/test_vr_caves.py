"""tools/vr_caves.py and data/vr_caves.json: Victory Road as one cave network, and the records that must agree with it.

Written by the test author, not by the session that wrote the tool or the data.

Three tiers here:
  - the tool's pure pieces, offline, on small hand-built input: runs() (the fill/setblock writer), shifts() and
    dilate() (the neighbour arithmetic everything else stands on), smooth() (no floor column more than one above a
    neighbour; locked flats hold; impossible locks refused), reach_bounds() (what a flat forces round it, through the
    footprint), check_fluids() (water and lava bounded), unit3()/u()/field() (the deterministic noise), base();
  - the committed data: each zone's core, find and pools, the pools' levels and prizes, the Slagworks' types, the
    vrc_* Habitat Block tiles (no overlap, clear of the EXP-033 rig) and the spawn-block policy, read straight from
    data/vr_caves.json, data/spawns.json, data/habitat_blocks.json, data/rewards.json, data/spawn_blocks.json and
    data/spawn_block_policy.json;
  - one real build (marked slow, about a minute each, two of them): it needs the canonical heightmap and the owner's
    annotated tracing (the Deep's pit and the region masks come from it) under COBBLERS_SOURCE_ROOT, and SKIPS,
    never passes, when either is absent or does not hash to its pin.

Not covered, and it needs a boot or a functional test:
  - that the written functions load and run (command limits, forceloading, /fill counts): lines() and write() are
    not called here; reapply's R9C test only checks that every listed function is run;
  - that the blocks the palettes name exist in the installed mod set: build() runs with no --server-dir, so every
    block resolves to its first choice and no fallback is exercised;
  - that the world matches the model after a run (`vr_caves.py verify --world <stopped copy>`);
  - that lava and water stay where the model puts them once the game ticks them, and that a player can in fact walk
    out: the walk-out is the tool's own voxel model of standing, stepping, swimming and falling, not Minecraft's;
  - that each Habitat Block spawns its pool at its levels in sealed rock (EXP-033), that the floor outside every
    tile spawns the pack's cave pools as the spec says, and that a find is granted in game.
"""
import hashlib
import json
import itertools
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import vr_caves as V  # noqa: E402


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


SPEC = _load("vr_caves.json")
SPAWNS = _load("spawns.json")
HABITATS = _load("habitat_blocks.json")
REWARDS = _load("rewards.json")
TRIGGERS = _load("spawn_blocks.json")["blocks"]
POLICY = _load("spawn_block_policy.json")
WORLD = _load("world.json")
RIFT_REGIONS = _load("rift_regions.json")
ZONES = SPEC["zones"]
CORED = [z for z in ZONES if z["id"] != "the_dark"]
POOLS = {h["id"]: h for h in SPAWNS["habitats"] if h["id"].startswith("vrc_")}
TILES = [b for b in HABITATS["blocks"] if b["id"].startswith("vrc_")]
BAND = SPEC["spawns"]["band"]
PRIZE_LEVELS = (60, 64)


def _levels(entry):
    lo, hi = str(entry["level"]).split("-")
    return int(lo), int(hi)


def _prize(zone_id):
    """The one species in a zone's core pool's rare bucket (asserted below to be exactly one)."""
    rare = [e for e in POOLS["vrc_%s_core" % zone_id]["entries"] if e["bucket"] == "rare"]
    return rare[0]["pokemon"] if len(rare) == 1 else None


# ------------------------------------------------------------------ runs()

def _expand(cmds):
    """The (x, y, z, block) cells a list of fill/setblock commands writes."""
    out = []
    for c in cmds:
        t = c.split()
        if t[0] == "setblock":
            out.append((int(t[1]), int(t[2]), int(t[3]), t[4]))
        else:
            assert t[0] == "fill", c
            x0, y0, z0, x1, y1, z1 = map(int, t[1:7])
            assert (x0, z0) == (x1, z1), "a column's fill leaves its column: %s" % c
            assert y1 > y0, "a fill of one cell (setblock is the single-cell form): %s" % c
            out += [(x0, y, z0, t[7]) for y in range(y0, y1 + 1)]
    return out


# Without it a column of identical blocks is written one setblock per cell: hundreds of thousands more commands,
# past the function limits tools/function_limits.py enforces. It also pins x = GX0 + i and z = GZ0 + k: a runs()
# that took world coordinates would write every column 3340 blocks east and 2460 south of where the model has it.
def test_runs_merges_a_consecutive_same_block_run_into_one_fill_at_the_grid_column():
    stone = "minecraft:stone"
    assert V.runs(4, 9, [(5, stone), (6, stone), (7, stone)]) == \
        ["fill %d 5 %d %d 7 %d %s" % (V.GX0 + 4, V.GZ0 + 9, V.GX0 + 4, V.GZ0 + 9, stone)]


# Without it a single cell is written as a fill of one: legal, but a second form for the verify and the function
# splitter to handle, and the sign of a run that failed to extend.
def test_runs_writes_a_single_cell_as_a_setblock():
    assert V.runs(0, 0, [(12, "minecraft:tuff")]) == ["setblock %d 12 %d minecraft:tuff" % (V.GX0, V.GZ0)]


# Without it a fill spans a gap in the column and writes a block into a cell the model left alone (in the shell
# pass, rock over the air the next pass is meant to carve; in the clear pass, rock into the Deep's pit).
def test_runs_never_merges_across_a_gap_in_the_column():
    cmds = V.runs(1, 1, [(3, "minecraft:tuff"), (4, "minecraft:tuff"), (6, "minecraft:tuff")])
    assert len(cmds) == 2
    assert (V.GX0 + 1, 5, V.GZ0 + 1, "minecraft:tuff") not in _expand(cmds)


# Without it a run of one block swallows the next block in the column: a lip becomes floor, a lava cell becomes rock.
def test_runs_never_merges_across_a_block_change():
    cmds = V.runs(2, 3, [(0, "minecraft:tuff"), (1, "minecraft:tuff"), (2, "minecraft:lava"), (3, "minecraft:lava")])
    assert sorted(_expand(cmds)) == sorted([(V.GX0 + 2, 0, V.GZ0 + 3, "minecraft:tuff"),
                                            (V.GX0 + 2, 1, V.GZ0 + 3, "minecraft:tuff"),
                                            (V.GX0 + 2, 2, V.GZ0 + 3, "minecraft:lava"),
                                            (V.GX0 + 2, 3, V.GZ0 + 3, "minecraft:lava")])
    assert len(cmds) == 2


# Without it some column of the model is written with a cell missing, doubled or moved; the three cases above are
# the edges, this is every shape a column can take (runs, gaps, changes, negative y) at once.
@pytest.mark.parametrize("seed", range(20))
def test_runs_writes_exactly_the_cells_it_is_given(seed):
    rnd = random.Random(seed)
    ys, y = [], rnd.randint(-24, 10)
    for _ in range(rnd.randint(1, 40)):
        y += rnd.choice((1, 1, 1, 2, 4))
        ys.append((y, rnd.choice(("minecraft:tuff", "minecraft:tuff", "minecraft:air", "minecraft:water"))))
    i, k = rnd.randint(0, V.NX - 1), rnd.randint(0, V.NZ - 1)
    got = _expand(V.runs(i, k, ys))
    assert sorted(got) == sorted((V.GX0 + i, yy, V.GZ0 + k, b) for yy, b in ys)


# ------------------------------------------------------------------ shifts(), dilate()

# Without it the four "neighbours" every flood (smooth, reach_bounds, dilate, the lake leak test) reads are not the
# four horizontal neighbours, or wrap round the grid's edge and tie the west side of the cave to the east.
def test_shifts_gives_each_cell_its_four_neighbours_and_the_fill_beyond_the_edge():
    a = np.arange(20).reshape(4, 5)
    got = V.shifts(a, -1)
    for i in range(4):
        for k in range(5):
            want = sorted(a[i + di, k + dk] if 0 <= i + di < 4 and 0 <= k + dk < 5 else -1
                          for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            assert sorted(int(s[i, k]) for s in got) == want, (i, k)


# Without it the clearance round the Deep's pit, the shell's two-column margin and the ravine's taken ring are not
# n steps wide: a dilate that overshoots carves less than the spec allows, one that undershoots cuts into the pit.
@pytest.mark.parametrize("n", [0, 1, 2, 4])
def test_dilate_grows_a_mask_by_exactly_n_steps(n):
    m = np.zeros((11, 11), bool)
    m[5, 5] = True
    got = V.dilate(m, n)
    ii, kk = np.indices(m.shape)
    assert (got == ((np.abs(ii - 5) + np.abs(kk - 5)) <= n)).all()


# Without it a mask on one edge of the grid bleeds onto the opposite edge.
def test_dilate_does_not_wrap_round_the_grid():
    m = np.zeros((6, 6), bool)
    m[0, 0] = True
    got = V.dilate(m, 1)
    assert got.sum() == 3 and not got[-1, 0] and not got[0, -1]


# ------------------------------------------------------------------ smooth()

def _net(F, foot=None, lock=None):
    n = V.Net()
    n.F = np.array(F, int)
    n.foot = np.ones(n.F.shape, bool) if foot is None else np.array(foot, bool)
    n.lock = np.zeros(n.F.shape, bool) if lock is None else np.array(lock, bool)
    return n


def _steps_ok(F, foot):
    """The pairs of foot neighbours more than one block apart (none, if the floor is walkable)."""
    bad = []
    for i in range(F.shape[0]):
        for k in range(F.shape[1]):
            if not foot[i, k]:
                continue
            for di, dk in ((1, 0), (0, 1)):
                ii, kk = i + di, k + dk
                if ii < F.shape[0] and kk < F.shape[1] and foot[ii, kk] and abs(int(F[i, k]) - int(F[ii, kk])) > 1:
                    bad.append(((i, k), (ii, kk), int(F[i, k]), int(F[ii, kk])))
    return bad


# Without it the floor has a step of two or more somewhere and the cave is not walkable end to end: the spec's
# promise that drops come from the ceiling and the lakes, never from a cliff (data/vr_caves.json floor).
@pytest.mark.parametrize("seed", range(6))
def test_smooth_leaves_no_floor_column_more_than_one_above_a_neighbour(seed):
    rnd = np.random.default_rng(seed)
    n = _net(rnd.integers(0, 30, (14, 17)))
    V.smooth(n)
    assert _steps_ok(n.F, n.foot) == []


# Without it smoothing with no flats could raise a floor into a ceiling the headroom check has already passed.
# (The docstring's claim: lowering alone is enough when nothing is locked.)
def test_smooth_without_locks_only_lowers_the_floor():
    rnd = np.random.default_rng(7)
    F0 = rnd.integers(0, 30, (10, 10))
    n = _net(F0)
    V.smooth(n)
    assert (n.F <= F0).all()


# Without it the ravine, the rest station, a lake's shore or a lava pool's lip is moved by the smoothing: the
# ravine no longer meets the apron, a pool's disc is no longer flat and lava meets bare floor.
@pytest.mark.parametrize("seed", range(4))
def test_smooth_holds_every_locked_column_and_still_leaves_no_step(seed):
    rnd = np.random.default_rng(100 + seed)
    F0 = rnd.integers(0, 30, (16, 16))
    lock = np.zeros(F0.shape, bool)
    lock[3:6, 3:6] = True                     # a flat at 20
    F0[3:6, 3:6] = 20
    lock[11:14, 10:14] = True                 # a flat at 12, well within reach of the first
    F0[11:14, 10:14] = 12
    n = _net(F0, lock=lock)
    V.smooth(n)
    assert (n.F[lock] == F0[lock]).all()
    assert _steps_ok(n.F, n.foot) == []


# Without it a column outside the footprint (rock) is given a floor, or rock between two caverns ties their floors
# together: two caverns that never meet would be dragged to the same height.
def test_smooth_leaves_rock_alone_and_does_not_join_floors_across_it():
    F0 = np.array([[0, 0, 0, -5, 30, 30, 30]] * 3)
    foot = np.array([[1, 1, 1, 0, 1, 1, 1]] * 3, bool)
    n = _net(F0, foot=foot)
    V.smooth(n)
    assert (n.F[:, 3] == -5).all()
    assert (n.F[:, :3] == 0).all() and (n.F[:, 4:] == 30).all()


# Without it two flats closer in steps than in height are "smoothed" by breaking one of them, and the cave is built
# with a cliff or a tilted lake instead of being refused.
def test_smooth_refuses_two_locks_further_apart_in_height_than_in_steps():
    F0 = np.array([[0, 0, 0, 5]])
    lock = np.array([[True, False, False, True]])     # 5 apart in height, 3 apart in steps
    with pytest.raises(V.CaveError, match="locked flats"):
        V.smooth(_net(F0, lock=lock))


# Without it the refusal above could be firing on any two locks; locks exactly as far apart in height as in steps
# can both hold, and must.
def test_smooth_accepts_two_locks_exactly_as_far_apart_in_height_as_in_steps():
    F0 = np.array([[0, 9, 9, 3]])
    lock = np.array([[True, False, False, True]])
    n = _net(F0, lock=lock)
    V.smooth(n)
    assert n.F.tolist() == [[0, 1, 2, 3]]


# ------------------------------------------------------------------ reach_bounds()

# Without it lock_flats() would lay a lake or a pool whose height no smoothing can reach from a flat already laid,
# and smooth() would refuse the whole build instead of the later flat being skipped.
def test_reach_bounds_widen_by_one_per_step_from_the_flat():
    n = _net(np.zeros((1, 6)))
    lo, hi = V.reach_bounds(n, np.array([[True] + [False] * 5]), 10)
    assert lo.tolist() == [[10, 9, 8, 7, 6, 5]]
    assert hi.tolist() == [[10, 11, 12, 13, 14, 15]]


# Without it steps are counted as the crow flies, and a flat just across a wall of rock is taken as within reach of
# one whose floors only meet the long way round (a cliff where the two tunnels join).
def test_reach_bounds_count_steps_through_the_footprint_not_through_rock():
    foot = np.array([[1, 0, 1],
                     [1, 0, 1],
                     [1, 1, 1]], bool)
    n = _net(np.zeros(foot.shape), foot=foot)
    mask = np.zeros(foot.shape, bool)
    mask[0, 0] = True
    lo, hi = V.reach_bounds(n, mask, 0)
    assert hi[0, 2] == 6 and lo[0, 2] == -6          # down, across and up: six steps, not two


# Without it a column the flat cannot reach at all (another body of cave, or rock) is bounded by it anyway.
def test_reach_bounds_leave_unreachable_columns_unbounded():
    foot = np.array([[1, 1, 0, 1]], bool)
    n = _net(np.zeros(foot.shape), foot=foot)
    lo, hi = V.reach_bounds(n, np.array([[True, False, False, False]]), 10)
    assert lo[0, 3] < -10 ** 5 and hi[0, 3] > 10 ** 5


# ------------------------------------------------------------------ check_fluids()

def _box(fill="minecraft:stone"):
    n = V.Net()
    n.B = V.Blocks()
    n.vol = np.full((5, 5, 6), n.B(fill), np.int16)
    n.falls = []
    return n


# Without it a pool or lake the model bounds on every side but up is reported as spilling, and no cave with water
# could ever be built.
def test_check_fluids_accepts_water_bounded_on_every_side_but_up():
    n = _box()
    n.vol[2, 2, 2] = n.B(V.WATER)
    n.vol[2, 2, 3] = n.B(V.AIR)
    assert V.check_fluids(n) == []


# Without it water beside air (a lake with a missing shore) is built and floods the floor round it.
@pytest.mark.parametrize("side", [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, -1)])
def test_check_fluids_reports_water_open_on_a_side_or_below(side):
    n = _box()
    n.vol[2, 2, 2] = n.B(V.WATER)
    n.vol[2 + side[0], 2 + side[1], 2 + side[2]] = n.B(V.AIR)
    assert len(V.check_fluids(n)) == 1


# Without it a lava fall's source (open below by design) is reported as a spill, or any lava cell open below is
# passed as a fall: only the cells in net.falls may pour down.
def test_check_fluids_lets_only_a_listed_fall_pour_down():
    n = _box()
    n.vol[2, 2, 3] = n.B(V.LAVA)
    n.vol[2, 2, 2] = n.B(V.AIR)
    assert [s[1] for s in V.check_fluids(n)] == ["down"]
    n.falls = [(V.GX0 + 2, V.GY0 + 3, V.GZ0 + 2)]
    assert V.check_fluids(n) == []


# ------------------------------------------------------------------ noise, base()

# Without it the cave differs from one build to the next (the records written by `records --write` stop matching
# the next build) and the feature densities in the spec are not the shares of columns they claim to be.
def test_unit3_is_deterministic_in_range_and_its_shares_match_their_thresholds():
    xs, zs = np.meshgrid(np.arange(V.GX0, V.GX0 + 200), np.arange(V.GZ0, V.GZ0 + 200), indexing="ij")
    a = V.unit3(xs, 1, zs, 900)
    assert (a == V.unit3(xs, 1, zs, 900)).all()
    assert a.shape == xs.shape and a.min() >= 0 and a.max() < 1
    for p in (0.004, 0.01, 0.1, 0.5):
        assert abs((a < p).mean() - p) < max(0.25 * p, 0.002), p
    assert (a != V.unit3(xs, 1, zs, 901)).mean() > 0.99      # another salt, another pattern


# Without it the caverns, their sizes and the loops of the tunnel graph change between builds, or cluster.
def test_u_is_deterministic_in_range_and_about_uniform():
    us = [V.u(90210, x, z) for x in range(150) for z in range(150)]
    assert us == [V.u(90210, x, z) for x in range(150) for z in range(150)]
    assert min(us) >= 0 and max(us) < 1
    assert abs(sum(us) / len(us) - 0.5) < 0.02
    assert V.u(1, 2) != V.u(2, 1)


# Without it the zone borders, the walls' alternation and the cavern outlines differ between builds, or the noise is
# spiky rather than smooth (zones would speckle instead of colliding along ragged borders).
@pytest.mark.parametrize("scale", [7, 17, 90])
def test_field_is_deterministic_bounded_and_smooth(scale):
    xs, zs = np.meshgrid(np.arange(V.GX0, V.GX0 + 160), np.arange(V.GZ0, V.GZ0 + 160), indexing="ij")
    f = V.field(SPEC["seed"], xs, zs, scale)
    assert (f == V.field(SPEC["seed"], xs, zs, scale)).all()
    assert np.abs(f).max() <= 1.7
    step = max(np.abs(np.diff(f, axis=0)).max(), np.abs(np.diff(f, axis=1)).max())
    assert step <= 20.0 / scale, step
    assert not np.allclose(f, V.field(SPEC["seed"] + 1, xs, zs, scale))


# Without it a block with state (a vine's age, a log's axis) is not recognised as open, as lava, or as whitelisted.
def test_base_strips_the_block_state_and_only_the_state():
    assert V.base("minecraft:cave_vines[age=25,berries=true]") == "minecraft:cave_vines"
    assert V.base("minecraft:lava") == "minecraft:lava"


# ------------------------------------------------------------------ the committed data

# Without it a zone has no core cavern to put its find and its prize in, or a find that names no reward, or no pool
# for its tiles: build() would raise in rest_and_finds or check_records, or the zone's tiles would name a pool
# spawns.json does not have.
@pytest.mark.parametrize("zone", CORED, ids=[z["id"] for z in CORED])
def test_every_zone_but_the_dark_has_a_core_a_find_and_its_two_pools(zone):
    assert zone["core"] and len(zone["core"]) == 2, zone["id"]
    by = {r["id"]: r for r in REWARDS["rewards"]}
    r = by.get(zone.get("find"))
    assert r, "%s's find %r is not a data/rewards.json record" % (zone["id"], zone.get("find"))
    want = "npc_grant" if zone["id"] == "abandoned_cut" else "cache"
    assert r["kind"] == want, (zone["id"], r["kind"])
    assert "vrc_%s" % zone["id"] in POOLS and "vrc_%s_core" % zone["id"] in POOLS


# Without it the Dark grows a find or a core pool that nothing places, or the base cave pool the Dark's tiles carry
# is missing.
def test_the_dark_has_no_core_and_its_tiles_draw_the_base_cave_pool():
    (dark,) = [z for z in ZONES if z["id"] == "the_dark"]
    assert dark["core"] is None and not dark.get("find")
    assert "vrc_cave" in POOLS


# Without it a pool named for no zone sits in spawns.json with nothing to place it, or a zone's pools go missing.
def test_the_vrc_pools_are_exactly_the_cave_pool_and_each_zones_pair():
    want = {"vrc_cave"} | {"vrc_%s%s" % (z["id"], s) for z in CORED for s in ("", "_core")}
    assert set(POOLS) == want


# Without it a pool spawns outside the level band the owner set for Victory Road (a level 40 Golbat under the
# League, or a level 70 one past the cap), or a prize comes in below 60.
@pytest.mark.parametrize("pool", sorted(POOLS))
def test_every_vrc_pool_spawns_inside_the_band_and_prizes_at_60_to_64(pool):
    h = POOLS[pool]
    assert (h["level_band"]["minimum"], h["level_band"]["maximum"]) == tuple(BAND), pool
    prizes = {_prize(z["id"]) for z in CORED}
    assert h["entries"], "%s is empty" % pool
    for e in h["entries"]:
        lo, hi = _levels(e)
        if e["pokemon"] in prizes:
            assert (lo, hi) == PRIZE_LEVELS, (pool, e["species"], e["level"])
        else:
            assert BAND[0] <= lo <= hi <= BAND[1], (pool, e["species"], e["level"])


# Without it a zone's core tiles carry no prize, or two, or the prize is not rare: the headline species stops being
# "rare, deep in its own zone" (data/vr_caves.json spawns).
@pytest.mark.parametrize("zone", CORED, ids=[z["id"] for z in CORED])
def test_each_core_pool_holds_exactly_one_rare_species_its_prize(zone):
    rare = [e["pokemon"] for e in POOLS["vrc_%s_core" % zone["id"]]["entries"] if e["bucket"] == "rare"]
    assert len(rare) == 1, (zone["id"], rare)


# Without it a zone's prize also spawns in its outer tiles, another zone's tiles or the Dark: it is no longer found
# only deep in its own zone.
@pytest.mark.parametrize("zone", CORED, ids=[z["id"] for z in CORED])
def test_a_zones_prize_appears_in_no_other_vrc_pool(zone):
    prize = _prize(zone["id"])
    assert prize
    elsewhere = [p for p, h in POOLS.items() if p != "vrc_%s_core" % zone["id"]
                 and any(e["pokemon"] == prize for e in h["entries"])]
    assert elsewhere == [], (prize, elsewhere)


# Without it a Dark or Ghost species spawns in the Slagworks, where the lava lights the floor to calm and
# fightorflight would keep it passive: the zone's design says there are none (data/vr_caves.json slagworks why).
@pytest.mark.parametrize("pool", ["vrc_slagworks", "vrc_slagworks_core"])
def test_the_slagworks_pools_hold_no_dark_or_ghost_type(pool):
    bad = [e["species"] for e in POOLS[pool]["entries"] if {"dark", "ghost"} & {t.lower() for t in e["types"]}]
    assert bad == []


# Without it the test below could pass over no tiles at all.
def test_the_cave_has_habitat_block_tiles_each_naming_a_vrc_pool_at_a_spec_range():
    assert TILES, "no vrc_* records in data/habitat_blocks.json"
    for b in TILES:
        assert b["pool"].startswith("cobblers:") and b["pool"].split(":", 1)[1] in POOLS, (b["id"], b["pool"])
        assert b["range_of_influence"] in SPEC["spawns"]["tile_ranges"], (b["id"], b["range_of_influence"])
        assert b.get("replace_spawns") is True, b["id"]


# Without it two tiles overlap and, per EXP-021, the overlap spawns nothing: a dead patch in the middle of the cave.
def test_no_two_vrc_habitat_blocks_overlap():
    bad = []
    for a, b in itertools.combinations(TILES, 2):
        d = math.hypot(a["position"]["x"] - b["position"]["x"], a["position"]["z"] - b["position"]["z"])
        if d < a["range_of_influence"] + b["range_of_influence"]:
            bad.append((a["id"], b["id"], round(d, 1)))
    assert bad == []


# Without it a cave tile reaches into the EXP-033 rig's range and the experiment measures two blocks at once.
def test_no_vrc_habitat_block_reaches_the_exp033_rig():
    rx, _ry, rz = SPEC["rig"]["habitat"]
    bad = [b["id"] for b in TILES
           if math.hypot(b["position"]["x"] - rx, b["position"]["z"] - rz) < b["range_of_influence"] + SPEC["rig"]["range"]]
    assert bad == []


def _victory_road_whitelist():
    out = {}
    for w in POLICY.get("whitelist") or []:
        if "victory road" in str(w.get("scope", "")).lower():
            for b in w["blocks"]:
                out[b] = str(w.get("why") or "").strip()
    return out


# Without it a block that conditions spawns (a Pokemon drawn to magma, a rail, a flower) is built into the cave
# without anyone having decided it may be, and the zone's pool is joined by species nobody chose. The tool accepts
# an empty "why" (vr_caves.whitelisted() maps the block to it and only checks presence); this does not.
@pytest.mark.parametrize("zone", ZONES, ids=[z["id"] for z in ZONES])
def test_every_spawn_conditioning_palette_block_is_whitelisted_for_victory_road_with_a_reason(zone):
    ok = _victory_road_whitelist()
    named = set(zone["palette"].values()) | set((zone.get("fallbacks") or {}).values())
    bad = [b for b in sorted(named) if V.base(b) in TRIGGERS and not ok.get(V.base(b))]
    assert bad == []


# ------------------------------------------------------------------ one real build (slow)

def _canonical_digest(net):
    """A hash of every cell's block name, independent of the order blocks were interned in."""
    names = net.B.names
    order = sorted(range(1, len(names)), key=lambda c: names[c])
    lut = np.zeros(len(names), np.int16)
    for rank, c in enumerate(order, start=1):
        lut[c] = rank
    h = hashlib.sha256()
    h.update(json.dumps([names[c] for c in order]).encode())
    h.update(np.ascontiguousarray(lut[net.vol]).tobytes())
    return h.hexdigest()


def _build_or_skip():
    import rift_deep as RD
    import terrain as T
    pytest.importorskip("PIL", reason="Pillow is needed to trace the Deep's pit from the annotated heightmap")
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the cave's cover is checked against the canonical heightmap")
    if not (Path(root) / WORLD["heightmap"]["path"]).is_file():
        pytest.skip("the canonical heightmap %s is not under COBBLERS_SOURCE_ROOT" % WORLD["heightmap"]["path"])
    ann = Path(root) / RIFT_REGIONS["source"]["file"].split(" ")[0]
    if not ann.is_file():
        pytest.skip("the owner's annotated tracing %s (the Deep's pit, the region masks) is not under "
                    "COBBLERS_SOURCE_ROOT" % ann.name)
    if hashlib.sha256(ann.read_bytes()).hexdigest() != RIFT_REGIONS["source"]["sha256"]:
        pytest.skip("the annotated tracing on disk is not the one data/rift_regions.json pins")
    try:
        plan, spec, net = V.build(root, None, strict=True)
    except (T.TerrainUnavailable, RD.DeepError) as e:  # unusable or unpinned inputs are a skip, named here
        pytest.skip("the build's inputs are unusable: %s" % e)
    digest = _canonical_digest(net)
    return plan, spec, digest


@pytest.fixture(scope="module")
def built():
    """(plan, spec, digest of every cell) from one real strict build, or a skip naming what is absent.

    V.build raising CaveError is NOT caught: a strict build that finds a problem fails the test that asked for it."""
    return _build_or_skip()


# Without it the cave can be built with a problem the tool knows about (thin cover, a leak, an open fluid face, an
# unwhitelisted block, records out of step): build(strict=True) raises on every one, and the fixture does not catch.
@pytest.mark.slow
def test_a_strict_build_raises_nothing_and_reports_no_problem(built):
    plan, _spec, _d = built
    assert plan["problems"] == []
    assert plan["records"] == []


# Without it the cave traps a player (a fall with no way back), hides floor nobody can reach, puts walkable floor
# against lava with no lip, or does not lead out onto the League's apron. Also asserts the walk saw something.
@pytest.mark.slow
def test_the_walk_reaches_the_exit_with_no_trap_no_unreached_floor_and_no_lava_without_a_lip(built):
    plan, _spec, _d = built
    w = plan["walk"]
    assert w["reachable"] > 0 and w["floor_cells"] > 0, "an empty walk proves nothing: %s" % w
    assert w["exit_reached"] is True, w
    assert (w["traps"], w["unreached_floor"], w["lava_without_lip"]) == (0, 0, 0), w


# Without it a roof sits under less rock than the spec's cover.min, and the surface above caves in or shows the
# cave to the sky (the cover is measured on the canonical heightmap, never a world).
@pytest.mark.slow
def test_the_least_cover_over_any_roof_is_at_least_the_spec_minimum(built):
    plan, spec, _d = built
    assert plan["counts"]["least cover"] >= spec["cover"]["min"], plan["counts"]


# Without it the model's tiles and finds and the committed records disagree: data/habitat_blocks.json places blocks
# where the cave has none, or a barrel's reward advancement fires where no barrel stands.
@pytest.mark.slow
def test_the_committed_tiles_and_finds_are_the_ones_the_model_puts(built):
    plan, _spec, _d = built
    by_id = {b["id"]: b for b in TILES}
    want = {"vrc_%02d" % n: t for n, t in enumerate(sorted(plan["tiles"], key=lambda t: (t["z"], t["x"])))}
    assert set(by_id) == set(want)
    for bid, t in want.items():
        b = by_id[bid]
        assert b["position"] == {"x": t["x"], "y": t["y"], "z": t["z"]}, bid
        assert b["pool"] == "cobblers:%s" % t["pool"] and b["range_of_influence"] == t["range"], bid
    assert sorted(plan["finds"]) == sorted(z["id"] for z in CORED)
    by = {r["id"]: r for r in REWARDS["rewards"]}
    for z in CORED:
        f, r = plan["finds"][z["id"]], by[z["find"]]
        if z["id"] == "abandoned_cut":
            assert f == {"npc": r["npc_at"]}, z["id"]
        else:
            assert f == {"cache": r["container"]["at"]}, z["id"]


# Without it the build's policy check could pass a block whitelisted with an empty reason (the tool only checks the
# block is listed): every spawn-conditioning block the model actually uses, palette or hard-coded, has one.
@pytest.mark.slow
def test_every_spawn_conditioning_block_the_model_uses_is_whitelisted_with_a_reason(built):
    plan, _spec, _d = built
    ok = _victory_road_whitelist()
    assert [b for b in plan["policy"] if not ok.get(b)] == []


# Without it the fights are fewer than the spec's count, or bunched nearer than min_apart. (That they split five and
# five round the rest station is not asserted: the plan does not carry the route.)
@pytest.mark.slow
def test_the_fights_are_the_spec_count_and_never_nearer_than_min_apart(built):
    plan, spec, _d = built
    st = plan["stands"]
    assert len(st) == spec["trainers"]["count"]
    for a, b in itertools.combinations(st, 2):
        assert math.hypot(a[0] - b[0], a[2] - b[2]) >= spec["trainers"]["min_apart"], (a, b)


# Without it two builds from the same inputs differ: `records --write` would write tiles the next build does not
# reproduce, and the strict check would fail at random (or, worse, a re-apply would carve a different cave).
@pytest.mark.slow
def test_two_builds_give_identical_tiles_finds_and_cells(built):
    plan, _spec, digest = built
    plan2, _spec2, digest2 = _build_or_skip()
    assert plan2["tiles"] == plan["tiles"]
    assert plan2["finds"] == plan["finds"] and plan2["stands"] == plan["stands"]
    assert digest2 == digest
