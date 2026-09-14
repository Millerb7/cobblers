"""River grading: the descending-path search and the heightmap cut.

The rule under test (tools/route_path.py, tools/grade_rivers.py): a river bed
never rises in the direction of flow. The surface P along a path is the lowest
ground met so far; ground above P costs a cut of (ground - P); water is flat at
its level and may only be entered at or below P + water_tol.

Expectations come from hand-built synthetic grids and from an independent
brute-force oracle written from that rule, not from previous tool output.

Not covered here: whether a graded course looks or behaves like a river in
Minecraft (water flow, WorldPainter import of the carved PNG, Axiom work), the
`plan` subcommand against real landmarks, and anything on the 8k heightmap.
"""
import hashlib
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import terrain as T            # noqa: E402
import route_path as R         # noqa: E402
import grade_rivers as G       # noqa: E402
import make_fixture as F       # noqa: E402

NAN = float("nan")


# ------------------------------------------------------------------ oracles


def _step(ground, water, x, z, P, tol):
    """The rule, written plainly: (cut, new P) entering (x, z), or None if blocked."""
    if water is not None and not math.isnan(water[z, x]):
        lv = float(water[z, x])
        if lv > P + tol:
            return None
        return 0.0, min(P, lv)
    g = float(ground[z, x])
    if g > P:
        return g - P, P
    return 0.0, g


def replay(ground, water, cells, source_level, tol=0.5):
    """Walk a returned path and recompute every cut and the surface profile."""
    P = float(source_level)
    cuts, prof = [], [P]
    for (x0, z0), (x1, z1) in zip(cells, cells[1:]):
        assert max(abs(x1 - x0), abs(z1 - z0)) == 1, "path is not 8-connected at %s->%s" % ((x0, z0), (x1, z1))
        s = _step(ground, water, x1, z1, P, tol)
        assert s is not None, "path enters water above its surface at %s" % ((x1, z1),)
        c, P = s
        cuts.append(c)
        prof.append(P)
    return cuts, prof


def brute_min_cut(ground, sources, source_level, goal, water=None, goal_cut=None, cap=math.inf, tol=0.5):
    """Smallest threshold t such that some descending path reaches a goal with every cut <= t.

    Feasibility at t is a BFS over (cell, surface) states; the answer is always 0, a
    step cut (ground - some reachable surface) or a goal's downstream cut, so a binary
    search over those candidates is exact. Goal cells end a path (they are not crossed).
    """
    h, w = ground.shape
    levels = {float(source_level)} | {float(v) for v in ground.ravel()}
    if water is not None:
        levels |= {float(v) for v in water.ravel() if not math.isnan(v)}
    cands = {0.0} | {float(g) - p for g in ground.ravel() for p in levels if g > p}
    if goal_cut is not None:
        cands |= {float(v) for v in goal_cut.ravel() if not math.isnan(v)}
    cands = sorted(c for c in cands if c <= cap)

    def feasible(t):
        seen = set()
        q = deque()
        for x, z in sources:
            st = (x, z, float(source_level))
            if st not in seen:
                seen.add(st)
                q.append(st)
        while q:
            x, z, P = q.popleft()
            for dx, dz in R.NEIGHBOURS:
                nx, nz = x + dx, z + dz
                if not (0 <= nx < w and 0 <= nz < h):
                    continue
                s = _step(ground, water, nx, nz, P, tol)
                if s is None or s[0] > t:
                    continue
                if goal[nz, nx]:
                    extra = goal_cut[nz, nx] if goal_cut is not None else NAN
                    if math.isnan(extra) or extra <= t:
                        return True
                    continue
                st = (nx, nz, s[1])
                if st not in seen:
                    seen.add(st)
                    q.append(st)
        return False

    lo, hi = 0, len(cands) - 1
    if hi < 0 or not feasible(cands[hi]):
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if feasible(cands[mid]):
            hi = mid
        else:
            lo = mid + 1
    return cands[lo]


def non_increasing(seq, eps=1e-9):
    return all(b <= a + eps for a, b in zip(seq, seq[1:]))


def tilted(h=10, w=7, top=100.0, drop=2.0):
    """Ground falling by `drop` per row toward z = h - 1; goal is the last row."""
    z = np.arange(h, dtype=np.float64)[:, None]
    ground = np.repeat(top - drop * z, w, axis=1)
    goal = np.zeros((h, w), bool)
    goal[-1, :] = True
    return ground, goal


# --------------------------------------------------------- descend_min_cut


def test_min_cut_on_a_tilted_plane_needs_no_cut():
    # breaks: a plain downhill valley would be reported as needing a gouge
    ground, goal = tilted()
    r = R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal)
    assert r is not None
    assert r["cut"] == 0.0
    assert goal[r["cells"][-1][1], r["cells"][-1][0]]
    assert r["cells"][0] == (3, 0)
    assert non_increasing(r["profile"])
    cuts, prof = replay(ground, None, r["cells"], ground[0, 3])
    assert max(cuts) == 0.0
    assert prof == pytest.approx(r["profile"])


@pytest.mark.parametrize("k", [1.0, 7.5, 23.25])
def test_min_cut_over_a_full_width_ridge_equals_its_height(k):
    # breaks: a ridge across the valley would be under- or over-reported, so rivers that
    # need a gouge would pass the MAX_GOUGE gate (or real ones would fail it)
    ground, goal = tilted(drop=1.0)
    ground[5, :] = ground[4, 0] + k           # k above the lowest surface reachable before it
    r = R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, cap=100.0)
    assert r["cut"] == pytest.approx(k, abs=1e-9)
    cuts, _ = replay(ground, None, r["cells"], ground[0, 3])
    assert max(cuts) == pytest.approx(k, abs=1e-9)
    assert non_increasing(r["profile"])


def test_min_cut_returns_none_when_the_ridge_is_deeper_than_cap():
    # breaks: courses that need a cut beyond cap would come back as routable
    ground, goal = tilted(drop=1.0)
    ground[5, :] = ground[4, 0] + 7.5
    assert R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, cap=7.0) is None
    assert R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, cap=7.5) is not None


def test_min_cut_takes_the_lower_of_two_saddles():
    # breaks: the search would settle for the first saddle found instead of the least cut
    ground, goal = tilted(h=10, w=9, drop=1.0)
    wall = 5
    base = ground[wall - 1, 0]
    ground[wall, :] = 1000.0
    ground[wall, 1] = base + 9.0              # high saddle, nearer the source column
    ground[wall, 7] = base + 3.0              # low saddle, far side
    r = R.descend_min_cut(ground, [(1, 0)], ground[0, 1], goal, cap=1e6)
    assert r["cut"] == pytest.approx(3.0)
    assert (7, wall) in r["cells"]


# ------------------------------------------------------------------- water


def test_water_above_the_running_surface_blocks_entry():
    # breaks: a river could be routed up into a lake standing above it
    ground, goal = tilted(drop=1.0)
    water = np.full(ground.shape, NAN)
    P = ground[4, 0]
    water[5, :] = P + 2.0                      # above P + water_tol
    assert R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, water=water, cap=1e6) is None


def test_water_within_tolerance_is_entered_without_changing_the_surface():
    # breaks: water_tol would be ignored and near-level lakes treated as walls, or it would raise P
    ground, goal = tilted(drop=1.0)
    water = np.full(ground.shape, NAN)
    P = ground[4, 0]
    water[5, :] = P + 0.4
    r = R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, water=water)
    assert r is not None and r["cut"] == 0.0
    i = next(i for i, (x, z) in enumerate(r["cells"]) if z == 5)
    assert r["profile"][i] == pytest.approx(P)


def test_water_at_or_below_the_surface_is_entered_flat_and_sets_the_surface():
    # breaks: a lake's level would not become the river surface, hiding the cut needed below it
    ground, goal = tilted(drop=1.0)
    water = np.full(ground.shape, NAN)
    P = ground[4, 0]
    level = P - 10.0
    ground[5, :] = 0.0                         # lake bed far below: must not matter, water is flat
    water[5, :] = level
    ground[6, :] = level + 2.0                 # ground just past the lake stands 2 above its level
    ground[7:, :] = level - 5.0                # and then falls away to the goal
    r =R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, water=water)
    i = next(i for i, (x, z) in enumerate(r["cells"]) if z == 5)
    assert r["profile"][i] == pytest.approx(level)
    assert r["cut"] == pytest.approx(2.0)
    assert non_increasing(r["profile"])


def test_goal_cut_raises_the_reported_cut_and_is_capped():
    # breaks: joining a body that itself needs a gouge downstream would look free
    ground, goal = tilted()
    gc = np.full(ground.shape, NAN)
    gc[-1, :] = 5.0
    r = R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, goal_cut=gc)
    assert r["cut"] == pytest.approx(5.0)
    assert R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, goal_cut=gc, cap=4.0) is None


def test_goal_cut_prefers_a_goal_with_no_downstream_cut():
    # breaks: the search would join the nearest body even when a free outlet is reachable
    ground, goal = tilted(w=9)
    gc = np.full(ground.shape, NAN)
    gc[-1, :] = 6.0
    gc[-1, 8] = NAN
    r = R.descend_min_cut(ground, [(0, 0)], ground[0, 0], goal, goal_cut=gc)
    assert r["cut"] == 0.0
    assert r["cells"][-1] == (8, ground.shape[0] - 1)


def test_goal_cut_applies_when_a_source_is_already_on_a_goal():
    # breaks: a course starting inside a body that needs a downstream gouge would report 0
    ground, goal = tilted()
    goal[0, 3] = True
    gc = np.full(ground.shape, NAN)
    gc[0, 3] = 5.0
    r = R.descend_min_cut(ground, [(3, 0)], ground[0, 3], goal, goal_cut=gc)
    assert r["cut"] == pytest.approx(5.0)


# ----------------------------------------------------------- descend_route


def _detour_grid():
    """A straight route over a 6-block ridge, and a long way round needing 2."""
    h, w = 12, 9
    ground, goal = tilted(h=h, w=w, drop=1.0)
    base = ground[5, 0]
    ground[6, :] = base + 6.0                  # ridge row
    ground[6, 8] = base + 2.0                  # gap at the far edge
    return ground, goal


def test_route_never_exceeds_max_cut_and_reaches_the_goal():
    # breaks: the cost router could cut deeper than the allowance plan grants it
    ground, goal = _detour_grid()
    src = [(1, 0)]
    r = R.descend_route(ground, src, ground[0, 1], goal, max_cut=3.0)
    assert r is not None
    cuts, prof = replay(ground, None, r["cells"], ground[0, 1])
    assert max(cuts) <= 3.0
    assert (8, 6) in r["cells"]
    assert goal[r["cells"][-1][1], r["cells"][-1][0]]
    assert prof == pytest.approx(r["profile"])
    assert non_increasing(r["profile"])


def test_route_returns_none_below_the_true_minimum_cut():
    # breaks: a course would be graded although no descending path fits the allowance
    ground, goal = _detour_grid()
    src = [(1, 0)]
    assert R.descend_min_cut(ground, src, ground[0, 1], goal)["cut"] == pytest.approx(2.0)
    assert R.descend_route(ground, src, ground[0, 1], goal, max_cut=1.9) is None


def test_route_with_a_large_allowance_may_take_the_short_cut():
    # breaks: max_cut would be ignored in the other direction (never allowing the cheaper cut)
    ground, goal = _detour_grid()
    r = R.descend_route(ground, [(1, 0)], ground[0, 1], goal, max_cut=10.0, cut_weight=0.0)
    cuts, _ = replay(ground, None, r["cells"], ground[0, 1])
    assert max(cuts) == pytest.approx(6.0)


# ------------------------------------------------------ random properties


def _random_case(rng, n=5, water_frac=0.15, with_goal_cut=True):
    ground = rng.integers(0, 16, size=(n, n)).astype(np.float64)
    water = np.where(rng.random((n, n)) < water_frac, rng.integers(0, 16, size=(n, n)).astype(float), NAN)
    goal = np.zeros((n, n), bool)
    goal[-1, :] = True
    water[0, :] = NAN
    gc = None
    if with_goal_cut:
        gc = np.where(rng.random((n, n)) < 0.5, rng.integers(0, 8, size=(n, n)).astype(float), NAN)
    xs = sorted(set(rng.integers(0, n, size=2).tolist()))
    sources = [(int(x), 0) for x in xs]
    level = float(rng.integers(4, 16))
    return ground, water, goal, gc, sources, level


@pytest.mark.parametrize("seed", range(40))
def test_min_cut_matches_brute_force_on_tiny_grids(seed):
    # breaks: the label-setting search would stop being exact (a pruning or ordering change)
    rng = np.random.default_rng(seed)
    ground, water, goal, gc, sources, level = _random_case(rng)
    cap = 9.0
    r = R.descend_min_cut(ground, sources, level, goal, water=water, goal_cut=gc, cap=cap)
    expect = brute_min_cut(ground, sources, level, goal, water=water, goal_cut=gc, cap=cap)
    if expect is None:
        assert r is None
        return
    assert r is not None
    assert r["cut"] == pytest.approx(expect)
    assert r["cells"][0] in sources
    ex, ez = r["cells"][-1]
    assert goal[ez, ex]
    assert not any(goal[z, x] for x, z in r["cells"][:-1])
    cuts, prof = replay(ground, water, r["cells"], level)
    assert prof == pytest.approx(r["profile"])
    assert non_increasing(r["profile"])
    extra = gc[ez, ex]
    worst = max(cuts + ([0.0] if math.isnan(extra) else [float(extra)]))
    assert worst == pytest.approx(r["cut"])


@pytest.mark.parametrize("seed", range(25))
def test_route_on_integer_grids_is_exact_about_feasibility(seed):
    # breaks: descend_route would miss a feasible course (or return one beyond max_cut); with
    # integer heights and levels, level_eps 0.5 prunes only truly dominated labels
    rng = np.random.default_rng(1000 + seed)
    ground, water, goal, _, sources, level = _random_case(rng, n=6, with_goal_cut=False)
    m = brute_min_cut(ground, sources, level, goal, water=water)
    if m is None:
        assert R.descend_route(ground, sources, level, goal, max_cut=1e9, water=water) is None
        return
    r = R.descend_route(ground, sources, level, goal, max_cut=m, water=water)
    assert r is not None
    cuts, prof = replay(ground, water, r["cells"], level)
    assert max(cuts, default=0.0) <= m
    assert non_increasing(r["profile"])
    assert prof == pytest.approx(r["profile"])
    if m > 0:
        assert R.descend_route(ground, sources, level, goal, max_cut=m - 0.5, water=water) is None


# ---------------------------------------------------------------- worst_cut


@pytest.mark.parametrize("profile,expected", [
    ([], (0.0, None)),
    ([5.0], (0.0, None)),
    ([10, 9, 9, 8], (0.0, None)),              # flat steps are not a rise
    ([10, 5, 8, 3], (3.0, 2)),
    ([5, 7, 6, 9], (4.0, 3)),                  # measured from the running minimum, not the previous point
    ([10, 4, 6, 2, 7], (5.0, 4)),              # a later, deeper rise from a new minimum wins
    ([10, 4, 9, 2, 5], (5.0, 2)),              # ties keep the first
])
def test_worst_cut_on_hand_made_profiles(profile, expected):
    # breaks: the cut check in `cut` and the plan's worst-cut figures would report the wrong rise
    worst, at = R.worst_cut(profile)
    assert worst == pytest.approx(expected[0])
    assert at == expected[1]


# -------------------------------------------------------------------- grade


def _stations(beds, spacing=1.0):
    return [(i * spacing, 0.0, float(b), -1) for i, b in enumerate(beds)]


@pytest.mark.parametrize("seed", range(10))
def test_grade_surface_is_the_running_minimum_clamped_at_sea(seed):
    # breaks: a graded surface could dip below sea level or rise downstream
    rng = np.random.default_rng(seed)
    sea = 62.0
    beds = (rng.random(60) * 60 + 40).tolist()
    start = float(rng.random() * 40 + 60)
    b, surface, worst, at, length = G.grade(_stations(beds), sea, start_level=start)
    assert all(s >= sea for s in surface)
    assert non_increasing(surface)
    assert b[0] == min(beds[0], start)
    run = math.inf
    for bed, s in zip(b, surface):
        run = min(run, bed)
        assert s == pytest.approx(max(run, sea))
    assert length == pytest.approx(59.0)


def test_grade_start_level_caps_the_first_station():
    # breaks: a lake outflow would start at its bed instead of the lake's water level
    b, surface, _, _, _ = G.grade(_stations([90, 85, 80]), 62.0, start_level=84.0)
    assert surface == [84.0, 84.0, 80.0]


def test_grade_worst_cut_is_measured_against_the_graded_surface():
    # breaks: the plan's worst_cut would disagree with the surface the cut is built from
    b, surface, worst, at, _ = G.grade(_stations([70, 50, 65]), 62.0)
    assert surface == [70.0, 62.0, 62.0]
    assert worst == pytest.approx(max(x - s for x, s in zip(b, surface)))


# ---------------------------------------------------------- simplify_graded


def _interp_floor(kept_idx, dist, floors, k):
    j = next(j for j in range(1, len(kept_idx)) if kept_idx[j] >= k)
    i0, i1 = kept_idx[j - 1], kept_idx[j]
    t = (dist[k] - dist[i0]) / ((dist[i1] - dist[i0]) or 1e-9)
    return floors[i0] + (floors[i1] - floors[i0]) * t


@pytest.mark.parametrize("seed", range(8))
def test_simplify_graded_keeps_endpoints_and_the_floor_within_half_a_block(seed):
    # breaks: the stored polyline would lose the grade (a floor that rises or drifts from the dense one)
    rng = np.random.default_rng(seed)
    n = 300
    x, z, y = 0.0, 0.0, 120.0
    pts = []
    heading = 0.0
    for i in range(n):
        pts.append((int(round(x)), int(round(z)), round(y, 2), round(y - 2, 2)))
        heading += rng.normal(0, 0.15)
        x += math.cos(heading)
        z += math.sin(heading)
        if rng.random() < 0.08:
            y -= float(rng.random() * 3)       # occasional drops, flat between: a graded surface
    pts = [p for i, p in enumerate(pts) if i == 0 or p[:2] != pts[i - 1][:2]]
    out = G.simplify_graded(pts)
    assert out[0] == pts[0] and out[-1] == pts[-1]
    assert len(out) < len(pts)
    kept = [i for i, p in enumerate(pts) if p in out]
    assert [pts[i] for i in kept] == out
    dist = [0.0]
    for a, b in zip(pts, pts[1:]):
        dist.append(dist[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    floors = [p[3] for p in pts]
    for k in range(len(pts)):
        assert abs(_interp_floor(kept, dist, floors, k) - floors[k]) <= 0.5 + 1e-9
    assert non_increasing([p[3] for p in out])
    dense = G.densify([list(p) for p in out])
    assert non_increasing([p[3] for p in dense])


def test_simplify_graded_short_inputs_are_returned_unchanged():
    # breaks: one- and two-point courses would be dropped or duplicated
    p = [(0, 0, 70.0, 68.0), (5, 0, 69.0, 67.0)]
    assert G.simplify_graded(p) == p
    assert G.simplify_graded(p[:1]) == p[:1]


def test_densify_steps_at_most_one_block_and_interpolates_linearly():
    # breaks: `cut` would skip columns between vertices or carve the wrong floor between them
    poly = [[0, 0, 80.0, 78.0], [10, 0, 70.0, 68.0], [10, 5, 70.0, 66.0]]
    d = G.densify(poly)
    assert tuple(d[0]) == tuple(poly[0]) and tuple(d[-1]) == tuple(poly[-1])
    for a, b in zip(d, d[1:]):
        assert math.hypot(b[0] - a[0], b[1] - a[1]) <= 1.0 + 1e-9
    at5 = next(p for p in d if p[0] == 5 and p[1] == 0)
    assert at5[3] == pytest.approx(73.0)


# ------------------------------------------------------------ open_sea_mask


def test_open_sea_is_edge_connected_below_sea_water_only():
    # breaks: an inland pit below sea level would become a river mouth
    below = np.zeros((12, 12), bool)
    below[:, 10:] = True                       # sea along the east edge
    below[3:6, 3:6] = True                     # enclosed pocket
    below[8, 6:10] = True                      # inlet joined to the sea
    below[1, 8] = True                         # touches the sea only diagonally via (2, 9)? no: see below
    below[2, 9] = True                         # joined 4-connected to (2, 10)
    m = G.open_sea_mask(below)
    assert m[:, 10:].all()
    assert not m[3:6, 3:6].any()
    assert m[8, 6:10].all()
    assert m[2, 9]
    assert not m[1, 8]                         # diagonal-only contact is not a connection (4-connected)
    assert not (m & ~below).any()


def test_open_sea_counts_water_on_any_edge():
    # breaks: a coast that does not touch the (0, 0) corner would not count as sea
    below = np.zeros((8, 8), bool)
    below[7, 3] = True
    below[4, 4] = True
    m = G.open_sea_mask(below)
    assert m[7, 3] and not m[4, 4]


# --------------------------------------------------------------- coarse grids


def test_coarse_grids_keep_a_one_block_channel_and_bound_the_penalty():
    # breaks: min-pooling would be lost and one-block channels vanish from the routing grid
    n = 64
    heights = np.full((n, n), 100.0, np.float32)
    heights[:, 13] = 70.0                      # one block wide
    heights[60:, :] = 40.0                     # sea along the south edge
    ymin, penalty, open_sea = G.coarse_grids(heights, 62.0)
    assert ymin.shape == (n // G.FACTOR, n // G.FACTOR)
    assert (ymin[:15, 13 // G.FACTOR] == 70.0).all()
    assert (penalty >= 0).all() and (penalty <= 3.0).all()
    assert open_sea[-1, :].all() and not open_sea[:14, :].any()
    flat = G.coarse_grids(np.full((n, n), 100.0, np.float32), 62.0)[1]
    assert np.allclose(flat, 0.0)


def test_water_bodies_mask_only_basin_cells_below_the_level():
    # breaks: lakes would be treated as flat water over ground that stands above their level
    ymin = np.full((16, 16), 100.0)
    ymin[4:8, 4:8] = 80.0
    lms = [
        {"id": "lake", "water_body": {"level_y": 90, "basin_polygons": [[[0, 0], [40, 0], [40, 40], [0, 40]]]}},
        {"id": "dry", "water_body": {"level_y": 50, "basin_polygons": [[[0, 0], [40, 0], [40, 40], [0, 40]]]}},
        {"id": "no_level", "water_body": {"level_y": None}},
        {"id": "not_water"},
    ]
    lakes, levels, ids = G.water_bodies(lms, ymin)
    assert [lk["id"] for lk in lakes] == ["lake"]
    assert (lakes[0]["mask"] == (ymin < 90)).all()
    assert (levels[4:8, 4:8] == 90).all()
    assert np.isnan(levels[ymin >= 90]).all()
    assert (ids[4:8, 4:8] == 0).all() and (ids[ymin >= 90] == -1).all()


def test_distance_heuristic_never_overestimates_the_path_length():
    # breaks: descend_route's A* would stop being optimal (and could miss the cheapest course)
    rng = np.random.default_rng(7)
    for n in (64, 66):
        goal = np.zeros((n, n), bool)
        for _ in range(3):
            goal[rng.integers(0, n), rng.integers(0, n)] = True
        h = G.distance_heuristic(goal)
        gz, gx = np.nonzero(goal)
        zz, xx = np.mgrid[0:n, 0:n]
        best = np.full((n, n), np.inf)
        for x, z in zip(gx, gz):
            dx, dz = np.abs(xx - x), np.abs(zz - z)
            octile = np.maximum(dx, dz) + (math.sqrt(2) - 1) * np.minimum(dx, dz)
            best = np.minimum(best, octile * G.FACTOR)
        assert h.shape == goal.shape
        assert (h <= best + 1e-9).all()
        assert (h[goal] == 0).all()


# --------------------------------------------------------- polyline helpers


def test_polyline_distance_is_distance_to_the_nearest_segment():
    # breaks: river ends near another carve would be misclassified as sources or confluences
    line = [(0, 0), (10, 0), (10, 10)]
    assert G.polyline_distance(line, 5, 0) == pytest.approx(0.0)
    assert G.polyline_distance(line, 5, 3) == pytest.approx(3.0)
    assert G.polyline_distance(line, -4, 3) == pytest.approx(5.0)      # clamps to the first vertex
    assert G.polyline_distance(line, 13, 5) == pytest.approx(3.0)
    assert G.polyline_distance([(0, 0)], 1, 1) == math.inf


def test_corridor_mask_covers_the_axis_and_not_far_cells():
    # breaks: along_channel would search outside (or miss) the band around the carve
    shape = (64, 64)
    line = [(20, 40), (200, 40)]
    m = G.corridor_mask(shape, line, 16)
    for x in range(20, 201, 8):
        assert m[40 // G.FACTOR, x // G.FACTOR]
    assert not m[40 // G.FACTOR + 8, 100 // G.FACTOR]
    assert not m[40 // G.FACTOR, 240 // G.FACTOR]


# ---------------------------------------------------- height_to_sample_floor


WORLDS = {
    "fixture": {"heightmap": {"bit_depth": 16},
                "import": {"input_units": "fraction_of_full_scale", "low_in": 0.0, "high_in": 1.0,
                           "low_out": 0, "high_out": 255, "clamp_low": True, "clamp_high": True}},
    "stretched": {"heightmap": {"bit_depth": 16},
                  "import": {"input_units": "fraction_of_full_scale", "low_in": 0.1, "high_in": 0.9,
                             "low_out": -64, "high_out": 320, "clamp_low": True, "clamp_high": True}},
}


@pytest.mark.parametrize("name", sorted(WORLDS))
def test_height_to_sample_floor_never_rounds_up(name):
    # breaks: `cut` could raise a column by a fraction of a block where it meant to lower it
    world = WORLDS[name]
    imp = world["import"]
    rng = np.random.default_rng(3)
    y = rng.uniform(imp["low_out"], imp["high_out"], 20000)
    s = G.height_to_sample_floor(y, world)
    back = T.sample_to_height(s.astype(np.uint16), world)
    assert (back <= y + 1e-9).all()
    step = (imp["high_out"] - imp["low_out"]) / ((imp["high_in"] - imp["low_in"]) * 65535.0)
    assert (y - back < step + 1e-9).all()


@pytest.mark.parametrize("name", sorted(WORLDS))
def test_height_to_sample_floor_inverts_sample_to_height_within_one_sample(name):
    # breaks: a planned floor would be carved more than one sample below where it was graded
    world = WORLDS[name]
    imp = world["import"]
    lo = int(math.ceil(imp["low_in"] * 65535))
    hi = int(math.floor(imp["high_in"] * 65535))
    samples = np.arange(lo, hi + 1, dtype=np.uint16)
    y = T.sample_to_height(samples, world)
    s = G.height_to_sample_floor(y, world).astype(np.int64)
    assert ((s == samples) | (s == samples.astype(np.int64) - 1)).all()


def test_height_to_sample_floor_clamps_to_the_sample_range():
    # breaks: a floor outside the import range would wrap around when cast to uint16
    world = WORLDS["stretched"]
    s = G.height_to_sample_floor(np.array([-500.0, 10000.0]), world)
    assert s[0] >= 0 and s[1] <= 65535


# --------------------------------------------------------------- cut, end to end


SIZE = 64
CH = {"half_width": 2, "depth": 2, "bank_slope": 1.0}


def _ground(size=SIZE):
    z, x = np.mgrid[0:size, 0:size].astype(np.float64)
    h = 110.0 - 0.1 * x
    h[15:18, 29:32] = 90.0                     # a pit on river_a's line, below its floor
    return h


def _build_world(tmp_path, heights):
    src_dir = tmp_path / "src"
    samples = F.to_samples(heights)
    png = F.write_png(src_dir / "land.png", samples)
    world = F.world_config(png, samples)
    wpath = tmp_path / "world.json"
    wpath.write_text(json.dumps(world), encoding="utf-8")
    return wpath, src_dir, png, world


def _course(cid, z, x0, x1, floor0, floor1, **extra):
    # one dry reach over the whole course (cobblers.rivers/1 now carries per-reach geometry; see
    # tests/test_river_character.py for the reach-by-reach cut): width 2 * half_width, centre depth 2
    reach = {"from_m": 0, "to_m": abs(x1 - x0), "catchment_km2": 1.0, "grade": 0.001, "water_body": False,
             "bank_slope": CH["bank_slope"], "bed": "SAND", "width": 2 * CH["half_width"], "depth": CH["depth"],
             "incision": 1.0}
    return dict({"id": cid, "valid": True, "reaches": [reach],
                 "graded_polyline": [[x0, z, floor0 + 2, floor0], [x1, z, floor1 + 2, floor1]],
                 "graded_polyline_fields": ["x", "z", "surface_y", "floor_y"]}, **extra)


def _plan(tmp_path, sha, courses):
    doc = {"schema": G.SCHEMA, "computed_from_sha256": sha, "courses": courses, "cut": None}
    p = tmp_path / "rivers.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _default_courses():
    return [
        _course("river_a", 16, 4, 56, 106.0, 101.0),
        _course("canal_b", 48, 4, 56, 104.0, 99.0, canal=True),
        _course("invalid_c", 32, 4, 56, 90.0, 80.0, valid=False),
    ]


def _run_cut(wpath, src_dir, plan, *extra, out_name="carved.png"):
    return G.main(["cut", "--world", str(wpath), "--source-root", str(src_dir),
                   "--plan", str(plan), "--out-name", out_name, *extra])


def _read(p):
    return np.array(Image.open(p)).astype(np.int64)


@pytest.fixture
def carved_world(tmp_path):
    heights = _ground()
    wpath, src_dir, png, world = _build_world(tmp_path, heights)
    plan = _plan(tmp_path, world["heightmap"]["sha256"], _default_courses())
    return wpath, src_dir, png, world, plan


def test_cut_writes_a_new_file_and_never_touches_the_source(carved_world):
    # breaks: the only copy of the source heightmap could be overwritten or silently changed
    wpath, src_dir, png, world, plan = carved_world
    before = hashlib.sha256(png.read_bytes()).hexdigest()
    dest = src_dir / "carved.png"
    assert not dest.exists()
    assert _run_cut(wpath, src_dir, plan) == 0
    assert dest.exists()
    assert hashlib.sha256(png.read_bytes()).hexdigest() == before == world["heightmap"]["sha256"]
    doc = json.loads(plan.read_text(encoding="utf-8"))
    assert doc["cut"]["output"]["path"] == "carved.png"
    assert doc["cut"]["output"]["sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()
    assert doc["cut"]["from_heightmap"]["sha256"] == before


def test_cut_only_lowers_and_reaches_the_floor(carved_world):
    # breaks: the carve could fill a pit or raise banks, or stop short of the graded floor
    wpath, src_dir, png, world, plan = carved_world
    _run_cut(wpath, src_dir, plan)
    src, out = _read(png), _read(src_dir / "carved.png")
    assert (out <= src).all()
    assert (out < src).any()
    assert (out[15:18, 29:32] == src[15:18, 29:32]).all()        # the pit below the floor is untouched
    y = T.sample_to_height(out, world)
    def floor_at(x):
        return 106.0 + (101.0 - 106.0) * (min(max(x, 4), 56) - 4) / 52.0

    for x in range(4, 57):
        assert y[16, x] <= floor_at(x) + 1e-9
        # a station half_width downstream is the deepest the centre may go (its parabola only rises from its floor)
        assert y[16, x] >= min(float(T.sample_to_height(src[16, x], world)), floor_at(x + CH["half_width"])) - 0.01


def test_cut_skips_canals_and_invalid_courses_unless_asked(carved_world):
    # breaks: courses the plan judged canals (or invalid) would be carved by default
    wpath, src_dir, png, world, plan = carved_world
    _run_cut(wpath, src_dir, plan)
    src, out = _read(png), _read(src_dir / "carved.png")
    assert (out[40:57, :] == src[40:57, :]).all()                # canal row and its banks unchanged
    assert (out[24:40, :] == src[24:40, :]).all()                # invalid course unchanged
    doc = json.loads(plan.read_text(encoding="utf-8"))
    assert doc["cut"]["courses_cut"] == ["river_a"]
    assert doc["cut"]["courses_not_cut"] == ["canal_b"]

    _run_cut(wpath, src_dir, plan, "--include-canals", out_name="with_canals.png")
    out2 = _read(src_dir / "with_canals.png")
    assert (out2[48, 4:57] < src[48, 4:57]).all()
    assert (out2 <= src).all()
    doc = json.loads(plan.read_text(encoding="utf-8"))
    assert sorted(doc["cut"]["courses_cut"]) == ["canal_b", "river_a"]


def test_cut_exclude_leaves_a_course_uncut(carved_world):
    # breaks: --exclude would be ignored and a course the user held back would be carved
    wpath, src_dir, png, world, plan = carved_world
    _run_cut(wpath, src_dir, plan, "--include-canals", "--exclude", "river_a")
    src, out = _read(png), _read(src_dir / "carved.png")
    assert (out[:32, :] == src[:32, :]).all()
    assert (out[48, 4:57] < src[48, 4:57]).all()
    doc = json.loads(plan.read_text(encoding="utf-8"))
    assert doc["cut"]["courses_cut"] == ["canal_b"]
    assert "river_a" in doc["cut"]["courses_not_cut"]


def test_cut_check_reports_no_floor_rise_and_bed_at_floor(carved_world):
    # breaks: the post-cut re-measure would stop certifying that the written bed descends
    wpath, src_dir, png, world, plan = carved_world
    _run_cut(wpath, src_dir, plan, "--include-canals")
    doc = json.loads(plan.read_text(encoding="utf-8"))
    checks = doc["cut"]["check"]["courses"]
    assert {c["course"] for c in checks} == {"river_a", "canal_b"}
    for c in checks:
        assert c["floor_rise_max"] == 0
        assert c["thalweg_above_floor_max"] == 0
    assert doc["cut"]["columns_lowered"] > 0
    assert doc["cut"]["lowered_blocks"]["max"] > 0


def test_cut_check_detects_a_rising_planned_floor(tmp_path):
    # breaks: a plan whose floor climbs would be cut and reported as clean
    wpath, src_dir, png, world = _build_world(tmp_path, _ground())
    plan = _plan(tmp_path, world["heightmap"]["sha256"], [_course("uphill", 40, 4, 56, 100.0, 104.0)])
    _run_cut(wpath, src_dir, plan)
    ck = json.loads(plan.read_text(encoding="utf-8"))["cut"]["check"]["courses"][0]
    assert ck["floor_rise_max"] == pytest.approx(4.0, abs=0.01)


def test_cut_refuses_a_plan_from_another_heightmap(carved_world):
    # breaks: a stale plan would be carved into a heightmap it was not computed from
    wpath, src_dir, png, world, _ = carved_world
    plan = _plan(src_dir.parent, "0" * 64, _default_courses())
    before = plan.read_bytes()
    with pytest.raises(SystemExit):
        _run_cut(wpath, src_dir, plan)
    assert not (src_dir / "carved.png").exists()
    assert plan.read_bytes() == before


def test_cut_refuses_to_overwrite_the_source_even_with_replace(carved_world):
    # breaks: --out-name equal to the source name would destroy the source heightmap
    wpath, src_dir, png, world, plan = carved_world
    before = png.read_bytes()
    for extra in ([], ["--replace"]):
        with pytest.raises(SystemExit):
            _run_cut(wpath, src_dir, plan, *extra, out_name=png.name)
    assert png.read_bytes() == before


def test_cut_refuses_an_existing_output_without_replace(carved_world):
    # breaks: a previous carve would be silently replaced
    wpath, src_dir, png, world, plan = carved_world
    _run_cut(wpath, src_dir, plan)
    first = (src_dir / "carved.png").read_bytes()
    with pytest.raises(SystemExit):
        _run_cut(wpath, src_dir, plan, "--include-canals")
    assert (src_dir / "carved.png").read_bytes() == first
    assert _run_cut(wpath, src_dir, plan, "--include-canals", "--replace") == 0


def test_cut_banks_reach_natural_ground(tmp_path):
    # breaks: a deep carve would leave cliffs at the edge of the bank window
    n = 128
    heights = np.full((n, n), 150.0)
    wpath, src_dir, png, world = _build_world(tmp_path, heights)
    plan = _plan(tmp_path, world["heightmap"]["sha256"], [_course("deep", 64, 8, 120, 100.0, 100.0)])
    _run_cut(wpath, src_dir, plan)
    y = T.sample_to_height(_read(src_dir / "carved.png"), world)
    one_sample = 255.0 / 65535.0
    hw, surface, floor = CH["half_width"], 102.0, 100.0
    for z in range(n):
        d = abs(z - 64)
        # parabola from the floor to one block under the water at the half width, then the bank slope
        section = floor + (surface - 1 - floor) * (d / hw) ** 2 if d <= hw else surface - 1 + CH["bank_slope"] * (d - hw)
        ideal = min(150.0, section)
        assert (y[z, 40:88] <= ideal + one_sample).all(), "bank above the slope at distance %d" % d
