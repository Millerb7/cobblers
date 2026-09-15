"""River character: drainage, reach sizing, cross-sections, per-reach cut, river paint, validator, region re-measure.

Covers tools/drainage.py, the character half of tools/grade_rivers.py (reach_character, cross_section,
lateral, characterise, finalize_course, farthest_descending_source, coastal_systems,
rivers_from_landmarks, base_heightmap, per-reach `cut`), tools/paint_maps.paint_rivers, the rivers
checks of tools/validate_data.py and tools/region_measure.measure.

Everything runs on synthetic grids and tmp_path fixtures. Expected values come from the rules as
written in the tool docstrings and CHARACTER_RULES, computed independently here, not from earlier
tool output.

Not covered: whether a cut channel holds water or looks like a river in Minecraft, whether
WorldPainter reads the per-column level crops as paint.js intends (only the manifest keys are
checked), the `plan` subcommand end to end, and anything on the real 8k heightmap. Those need a
WorldPainter run and an in-game look recorded as an experiment.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import terrain as T              # noqa: E402
import drainage as D             # noqa: E402
import grade_rivers as G         # noqa: E402
import make_fixture as F         # noqa: E402
import paint_maps as PP          # noqa: E402
import region_measure as RM      # noqa: E402
import validate_data as V        # noqa: E402

SEA = 62.0
ONE_SAMPLE = 255.0 / 65535.0     # make_fixture import: 0..255 over the full 16-bit range


def non_increasing(seq, eps=1e-9):
    return all(b <= a + eps for a, b in zip(seq, seq[1:]))


# ======================================================================= drainage


def _chain_to_sea(dirs, open_sea, z, x):
    """Follow D8 receivers; returns the terminal cell and whether it is sea. Fails on a cycle."""
    h, w = dirs.shape
    for _ in range(h * w + 1):
        if open_sea[z, x]:
            return (z, x), True
        r = D.receiver(dirs, z, x)
        if r is None:
            return (z, x), False
        z, x = r
    raise AssertionError("D8 chain from a land cell did not terminate: cycle")


def _sea_row(h, w):
    sea = np.zeros((h, w), bool)
    sea[-1, :] = True
    return sea


def _v_valley(n=16):
    """Ground falling toward the centre column and toward the sea, which is one cell at the south end."""
    z, x = np.mgrid[0:n, 0:n].astype(np.float64)
    c = n // 2
    h = 100.0 + 3.0 * np.abs(x - c) - 2.0 * z
    sea = np.zeros((n, n), bool)
    sea[n - 1, c] = True
    h[n - 1, :] = 1000.0
    h[n - 1, c] = 0.0
    return h, sea


# removing this lets priority flood lower ground, which would carve drainage below the authored surface
def test_priority_flood_never_lowers_and_raises_sea_to_sea_level():
    rng = np.random.default_rng(1)
    h = rng.uniform(40, 120, (20, 20))
    sea = _sea_row(20, 20)
    filled, order = D.priority_flood(h, sea, SEA)
    assert (filled >= h - 1e-12).all()
    assert (filled[sea] >= SEA).all()
    land = np.flatnonzero(~sea.ravel()).tolist()
    assert sorted(order) == land, "every land cell is settled exactly once; open sea is never queued"


# removing this lets closed basins keep their pits, so catchment stops at a hollow instead of the sea
@pytest.mark.parametrize("seed", range(6))
def test_every_interior_land_cell_drains_to_the_sea_without_cycles(seed):
    rng = np.random.default_rng(seed)
    n = 18
    h = rng.uniform(70, 130, (n, n))
    h[:, 0] = h[:, -1] = h[0, :] = 200.0          # high rim: the only way out is the sea row
    h[-1, :] = 30.0
    sea = _sea_row(n, n)
    h[5:9, 5:9] = 60.0                             # a closed pit, below sea level but not open sea
    filled, order = D.priority_flood(h, sea, SEA)
    dirs = D.d8(filled, sea)
    assert (dirs[sea] == -1).all()
    for z in range(n):
        for x in range(n):
            if sea[z, x] or z == 0 or x == 0 or x == n - 1:
                continue
            _, to_sea = _chain_to_sea(dirs, sea, z, x)
            assert to_sea, "cell %s ends in a land sink" % ((z, x),)


# removing this lets flats (equal heights) become sinks: D8 has no strictly lower neighbour without epsilon
def test_epsilon_lets_a_perfect_flat_drain():
    n = 12
    h = np.full((n, n), 80.0)
    h[:, 0] = h[:, -1] = h[0, :] = 200.0          # rim above the flat: see the map-edge xfail below
    h[-1, :] = 40.0
    sea = _sea_row(n, n)
    filled, order = D.priority_flood(h, sea, SEA)
    dirs = D.d8(filled, sea)
    for z in range(1, n - 1):
        for x in range(1, n - 1):
            assert _chain_to_sea(dirs, sea, z, x)[1], (z, x)


# removing this lets accumulation lose or double-count cells, so every catchment and channel size is wrong
def test_accumulation_at_the_single_outlet_counts_every_land_cell():
    h, sea = _v_valley()
    filled, order = D.priority_flood(h, sea, SEA)
    dirs = D.d8(filled, sea)
    acc = D.accumulation(dirs, order)
    n = h.shape[0]
    mouths = [(z, x) for z in range(n) for x in range(n)
              if not sea[z, x] and D.receiver(dirs, z, x) is not None and sea[D.receiver(dirs, z, x)]]
    land = int((~sea).sum())
    assert sum(acc[m] for m in mouths) == pytest.approx(land)
    assert acc[sea].sum() == pytest.approx(land + 1)
    assert (acc >= 1).all()


# removing this lets a land hollow on the map edge become a sink that never reaches the sea
def test_a_hollow_on_the_map_edge_still_drains_to_the_sea():
    n = 8
    z = np.arange(n)[:, None]
    h = np.repeat(100.0 - 2.0 * z, n, axis=1)
    h[-1, :] = 0.0
    sea = _sea_row(n, n)
    h[0, 3] = 80.0
    filled, order = D.priority_flood(h, sea, SEA)
    dirs = D.d8(filled, sea)
    assert _chain_to_sea(dirs, sea, 1, 3)[1]


def test_receiver_follows_nb_and_is_none_for_sinks():
    # removing this lets receiver() and NB disagree on axis order ((dz, dx)), sending flow sideways
    dirs = np.full((3, 3), -1, np.int8)
    dirs[1, 1] = D.NB.index((1, 0))
    assert D.receiver(dirs, 1, 1) == (2, 1)
    assert D.receiver(dirs, 0, 0) is None


# ================================================================ reach_character


def _rc(A=1.0, g=0.005, water=False, major=None):
    return G.reach_character(0, 64, A, g, water, major)


# removing this lets a bigger catchment give a narrower or shallower river
def test_width_and_depth_never_shrink_with_catchment():
    for g in (0.0005, 0.005, 0.05):
        rows = [_rc(A, g) for A in (0.0, 0.05, 0.25, 1, 4, 10, 40, 200)]
        assert non_increasing([-r["width"] for r in rows])
        assert non_increasing([-r["depth"] for r in rows])
        assert all(3 <= r["width"] <= 19 for r in rows)
        assert all(1.0 <= r["depth"] <= 4.5 for r in rows)


# removing this lets fast and slow water get the same section, against the speed rule
def test_slower_water_is_wider_with_a_shallower_bank():
    slow, fast = _rc(1.0, 0.0008), _rc(1.0, 0.03)
    assert slow["width"] > fast["width"]
    assert slow["bank_slope"] < fast["bank_slope"]
    assert slow["depth"] == fast["depth"], "depth is set by catchment only"
    # rule: width = (3 + 4.5 sqrt A) * speed, speed = (g / 0.005) ** -0.2 clamped 0.75..1.3
    assert slow["width"] == round(7.5 * 1.3)
    assert fast["width"] == round(7.5 * max(0.75, (0.03 / 0.005) ** -0.2))


# removing this lets the bank-slope end points drift from the documented 0.4 / 2.0
def test_bank_slope_end_points_and_monotonic_in_grade():
    grades = [1e-4, 0.001, 0.002, 0.005, 0.01, 0.02, 0.0317, 0.1]
    banks = [_rc(1.0, g)["bank_slope"] for g in grades]
    assert banks[0] == 0.4 and banks[1] == 0.4
    assert banks[-1] == 2.0 and banks[-2] == 2.0
    assert non_increasing([-b for b in banks])


# removing this lets the rule written into rivers.json drift from what the code does
def test_bank_slope_is_two_at_the_documented_grade():
    assert "0.0316" in G.CHARACTER_RULES["bank_slope"]
    assert _rc(1.0, 10 ** -1.5)["bank_slope"] == 2.0
    assert _rc(1.0, 0.03)["bank_slope"] < 2.0


@pytest.mark.parametrize("g,bed", [(0.2, "GRAVEL"), (0.01, "GRAVEL"), (0.00999, "SAND"), (0.0025, "SAND"),
                                   (0.00249, "CLAY"), (1e-4, "CLAY")])
def test_bed_material_thresholds(g, bed):
    # removing this lets a steep reach be painted clay or a sluggish one gravel
    assert _rc(1.0, g)["bed"] == bed


# removing this lets ordinary rivers be incised like the major river, or the major river not at all
def test_incision_is_freeboard_on_rivers_and_scales_on_the_major_river():
    assert _rc(5.0, 0.005)["incision"] == G.FREEBOARD == 1.0
    assert _rc(100.0, 0.005, major=100.0)["incision"] == G.MAJOR_INCISION
    assert _rc(25.0, 0.005, major=100.0)["incision"] == pytest.approx(G.MAJOR_INCISION * 0.5, abs=0.05)
    assert _rc(0.5, 0.005, major=100.0)["incision"] == 1.0          # 8 * sqrt(0.005) < 1: freeboard wins
    assert _rc(400.0, 0.005, major=100.0)["incision"] == G.MAJOR_INCISION, "share is capped at 1"


# removing this lets a narrow river get a floodplain, or the wide major river lose its valley
def test_valley_only_on_major_reaches_at_least_sixteen_wide():
    assert "valley" not in _rc(40.0, 0.001), "not major: no valley however wide"
    for A in (0.5, 2, 10, 30, 60, 100):
        r = _rc(A, 0.005, major=100.0)
        # the rule is on the unrounded width; the stored width is rounded, so 16 itself can go either way
        if "valley" in r:
            assert r["width"] >= G.MAJOR_VALLEY_WIDTH, (A, r["width"])
        else:
            assert r["width"] <= G.MAJOR_VALLEY_WIDTH, (A, r["width"])
    assert "valley" in _rc(100.0, 0.005, major=100.0) and "valley" not in _rc(0.5, 0.005, major=100.0)
    full = _rc(100.0, 0.005, major=100.0)
    v = full["valley"]
    assert v["floodplain_above_water"] == 1
    assert [t["rise"] for t in v["terraces"]] == [5, 5]
    fp = min(48.0, max(10.0, 10.0 + 0.6 * full["width"] * math.sqrt(0.01 / 0.005)))
    assert v["floodplain_width"] == pytest.approx(fp, abs=1.0)
    assert v["terraces"][0]["tread"] == pytest.approx(0.6 * fp, abs=1.0)
    assert v["terraces"][1]["tread"] == pytest.approx(0.4 * fp, abs=1.0)
    assert v["wall_slope"] == 0.6 and v["riser_slope"] >= 0.8
    assert 10 <= v["floodplain_width"] <= 48


def test_major_width_and_depth_reach_the_major_scale_at_the_mouth():
    # removing this lets the major river be sized like any other river at its mouth
    r = _rc(100.0, 0.005, major=100.0)
    assert r["width"] == 30
    assert r["depth"] == 9.0


# ========================================================= cross_section / lateral


def _reach(width=8, bank=1.5, valley=None):
    r = {"from_m": 0, "to_m": 64, "catchment_km2": 1.0, "grade": 0.005, "water_body": False,
         "bank_slope": bank, "bed": "SAND", "width": width, "depth": 3.0, "incision": 1.0}
    if valley:
        r["valley"] = valley
    return r


VALLEY = {"floodplain_width": 12, "floodplain_above_water": 1,
          "terraces": [{"rise": 5, "tread": 7}, {"rise": 5, "tread": 5}], "riser_slope": 1.0, "wall_slope": 0.6}


def _profile_by_rule(d, surface, floor, reach):
    """The lateral profile written from the tool's docstrings, independently of lateral()."""
    hw, s = reach["width"] / 2.0, reach["bank_slope"]
    edge = surface - 1.0
    if d <= hw:
        return floor + (edge - floor) * (d / hw) ** 2
    v = reach.get("valley")
    if not v:
        return edge + s * (d - hw)
    fp = surface + v["floodplain_above_water"]
    k = hw + (fp - edge) / s
    if d <= k:
        return edge + s * (d - hw)
    y = fp
    k2 = k + v["floodplain_width"]
    if d <= k2:
        return fp
    for t in v["terraces"]:
        run = t["rise"] / v["riser_slope"]
        if d <= k2 + run:
            return y + v["riser_slope"] * (d - k2)
        k2 += run
        y += t["rise"]
        if d <= k2 + t["tread"]:
            return y
        k2 += t["tread"]
    return y + v["wall_slope"] * (d - k2)


@pytest.mark.parametrize("valley", [None, VALLEY])
def test_lateral_matches_the_documented_section(valley):
    # removing this lets the carved section drift from the parabola / bank / floodplain / terrace rule
    reach = _reach(width=16 if valley else 7, valley=valley)
    d = np.linspace(0, 90, 3601)
    got = G.lateral(d, 100.0, 94.0, reach)
    want = np.array([_profile_by_rule(float(x), 100.0, 94.0, reach) for x in d])
    assert np.allclose(got, want, atol=1e-9)


@pytest.mark.parametrize("valley", [None, VALLEY])
def test_lateral_centre_edge_continuity_and_monotonic(valley):
    # removing this lets the bed step at the channel edge or a knot, or a bank dip back down
    reach = _reach(width=16 if valley else 7, valley=valley)
    hw = reach["width"] / 2.0
    surface, floor = 100.0, 94.0
    assert float(G.lateral(np.array(0.0), surface, floor, reach)) == floor
    assert float(G.lateral(np.array(hw), surface, floor, reach)) == pytest.approx(surface - 1.0)
    ks, ys, wall, hw2 = G.cross_section(reach, surface, floor)
    assert hw2 == hw and ks[0] == hw and ys[0] == surface - 1.0
    for k, y in zip(ks, ys):
        lo, hi = G.lateral(np.array([k - 1e-7, k + 1e-7]), surface, floor, reach)
        assert lo == pytest.approx(y, abs=1e-5) and hi == pytest.approx(y, abs=1e-5)
    d = np.linspace(0, 120, 12001)
    assert non_increasing(list(-G.lateral(d, surface, floor, reach)), eps=1e-9)


def test_valley_knots_floodplain_one_above_water_and_terraces_rise():
    # removing this lets the floodplain flood (at or below water) or the terraces lose their risers
    reach = _reach(width=16, bank=2.0, valley=VALLEY)
    ks, ys, wall, hw = G.cross_section(reach, 100.0, 94.0)
    assert ys[1] == ys[2] == 101.0
    assert ks[2] - ks[1] == VALLEY["floodplain_width"]
    assert ys[3] - ys[2] == 5 and ys[4] == ys[3]
    assert ks[4] - ks[3] == 7
    assert ys[5] - ys[4] == 5 and ys[6] == ys[5] and ks[6] - ks[5] == 5
    assert wall == 0.6


# ================================================================ finalize_course


def _synthetic_course(rng, n=240, lake_head=0, lake_mid=None, end_body=False):
    """Stations one block apart along x; beds with random drops; optional lake stations at the head or middle."""
    beds, ids, y = [], [], 130.0
    for i in range(n):
        if rng.random() < 0.1:
            y -= float(rng.random() * 2.5)
        b = y + float(rng.random() * 3)
        lid = -1
        if i < lake_head:
            lid = 0
        if lake_mid and lake_mid[0] <= i < lake_mid[1]:
            lid = 0
        beds.append(b)
        ids.append(lid)
    st = [(i, 40, b, l) for i, (b, l) in enumerate(zip(beds, ids))]
    bodies = [{"id": "lake", "kind": "lake"}]
    if lake_head:
        level = min(beds[:lake_head])
        st = [(x, z, level if l >= 0 else b, l) for x, z, b, l in st]
    _, surface, _, _, _ = G.grade(st, SEA, st[0][2] if lake_head else None)
    return st, surface, bodies


def _finalize(monkeypatch, st, surface, bodies, source_kind="inland_end", major=False, simplify=False):
    if not simplify:
        monkeypatch.setattr(G, "simplify_graded", lambda pts: list(pts))
    ctx = {"dense": {"c": (st, surface)}, "bodies": bodies}
    km2 = np.tile(np.linspace(0.2, 6.0, max(1, len(st) // G.FACTOR + 2)), (40 // G.FACTOR + 2, 1))
    reaches, chain, total = G.characterise(ctx, "c", km2, major)
    row = {"id": "c", "source": {"kind": source_kind}}
    G.finalize_course(ctx, row, [dict(r) for r in reaches], chain, total)
    return row, reaches, chain


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("from_lake", [False, True])
def test_finalized_surface_and_floor_descend_and_respect_their_limits(monkeypatch, seed, from_lake):
    # removing this lets the stored water surface rise, fall below the level the course ends in, cut into
    # its own lake, or let a bed stand above surface - depth
    rng = np.random.default_rng(seed)
    st, surface, bodies = _synthetic_course(rng, lake_head=20 if from_lake else 0)
    row, reaches, chain = _finalize(monkeypatch, st, surface, bodies,
                                    "lake_outflow" if from_lake else "inland_end", major=bool(seed % 2))
    poly = row["graded_polyline"]
    assert len(poly) == len(st)
    level = [p[2] for p in poly]
    floor = [p[3] for p in poly]
    assert non_increasing(level) and non_increasing(floor)
    end = surface[-1]
    depth = G.depth_profile(reaches, chain)
    wet = [s[3] >= 0 for s in st]
    first_dry = next(chain[i] for i, w in enumerate(wet) if not w)
    for k in range(len(st)):
        assert level[k] >= end - 0.01, "below the level the course ends in"
        assert level[k] <= surface[k] + 0.01, "the surface is only let down"
        assert floor[k] <= level[k] - depth[k] + 0.011
        if wet[k]:
            assert level[k] == pytest.approx(surface[k], abs=0.01), "incision on a lake station"
        if from_lake:
            assert level[k] >= surface[k] - G.INCISION_TAPER * max(0.0, chain[k] - first_dry) - 0.011


def test_finalize_keeps_endpoints_rescales_reaches_and_summarises(monkeypatch):
    # removing this lets reach chainages point past the stored polyline, so `cut` and paint use the wrong reach
    rng = np.random.default_rng(11)
    st, surface, bodies = _synthetic_course(rng, lake_head=15)
    row, _, chain = _finalize(monkeypatch, st, surface, bodies, "lake_outflow", simplify=True)
    poly = row["graded_polyline"]
    assert poly[0][:2] == [st[0][0], st[0][1]] and poly[-1][:2] == [st[-1][0], st[-1][1]]
    assert len(poly) < len(st)
    assert row["graded_polyline_fields"] == ["x", "z", "surface_y", "floor_y"]
    reaches = row["reaches"]
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(poly, poly[1:]))
    assert reaches[0]["from_m"] == 0 and reaches[-1]["to_m"] == round(length)
    for a, b in zip(reaches, reaches[1:]):
        assert a["to_m"] == b["from_m"], "reaches must tile the course"
    assert reaches[0]["water_body"] and not reaches[-1]["water_body"]
    ch = row["character"]
    assert set(ch) == {"width", "depth", "bank_slope", "catchment_km2", "bed_share_pct"}
    assert ch["width"][0] <= ch["width"][1]


# removing this lets a lake crossed mid-course be drained into the river below it by the upstream incision
def test_a_lake_crossed_mid_course_keeps_its_level(monkeypatch):
    beds, ids = [], []
    for x in range(200):
        if x < 50:
            beds.append(110.0 - 10.0 * x / 50)
            ids.append(-1)
        elif x < 100:
            beds.append(100.0)
            ids.append(0)
        else:
            beds.append(100.0 - 10.0 * (x - 100) / 100)
            ids.append(-1)
    st = [(x, 0, b, l) for x, (b, l) in enumerate(zip(beds, ids))]
    _, surface, _, _, _ = G.grade(st, SEA)
    row, _, _ = _finalize(monkeypatch, st, surface, [{"id": "lake", "kind": "lake"}])
    for x in range(50, 100):
        assert row["graded_polyline"][x][2] == pytest.approx(100.0, abs=0.01)


def test_characterise_reaches_tile_split_at_water_and_catchment_never_falls():
    # removing this lets a reach straddle a lake shore or report less catchment than a reach above it
    rng = np.random.default_rng(4)
    st, surface, bodies = _synthetic_course(rng, lake_mid=(90, 130))
    ctx = {"dense": {"c": (st, surface)}, "bodies": bodies}
    km2 = rng.uniform(0.1, 3.0, (20, 80))
    reaches, chain, total = G.characterise(ctx, "c", km2)
    assert reaches[0]["from_m"] == 0 and reaches[-1]["to_m"] == round(total)
    for a, b in zip(reaches, reaches[1:]):
        assert a["to_m"] == b["from_m"]
        assert b["catchment_km2"] >= a["catchment_km2"]
    assert any(r["water_body"] for r in reaches)
    for r in reaches:
        assert r["to_m"] - r["from_m"] <= G.REACH + 1
        inner = [s[3] >= 0 for s, c in zip(st, chain) if r["from_m"] < c < r["to_m"]]
        assert len(set(inner)) <= 1, "a reach mixes lake and river stations"


def test_depth_profile_eases_between_reach_midpoints():
    # removing this lets the bed step by a whole depth at a reach boundary
    reaches = [dict(_reach(), from_m=0, to_m=64, depth=2.0), dict(_reach(), from_m=64, to_m=128, depth=4.0)]
    d = G.depth_profile(reaches, [0, 32, 64, 96, 128])
    assert list(d) == [2.0, 2.0, 3.0, 4.0, 4.0]
    assert G.at_chainage(reaches, 64)["depth"] == 2.0 and G.at_chainage(reaches, 64.5)["depth"] == 4.0
    assert G.at_chainage(reaches, 999)["depth"] == 4.0


# ===================================================== farthest_descending_source


def _valley_ctx(h=20, w=40):
    z, x = np.mgrid[0:h, 0:w].astype(np.float64)
    ymin = 70.0 + x + 2.0 * np.abs(z - h // 2)
    sea = np.zeros((h, w), bool)
    sea[:, 0] = True
    ymin[:, 0] = 40.0
    return {"ymin": ymin, "levels": np.full((h, w), np.nan), "open_sea": sea}


def _octile(a, b):
    dz, dx = abs(a[0] - b[0]), abs(a[1] - b[1])
    return (max(dz, dx) + (math.sqrt(2) - 1) * min(dz, dx)) * G.FACTOR


# removing this lets the major river's head be a nearby cell instead of the far upstream end of its system
def test_farthest_source_is_the_far_upstream_end_of_a_valley():
    ctx = _valley_ctx()
    (hz, hx), far = farthest = G.farthest_descending_source(ctx, [(10, 1)])
    assert hx == 39 and hz in (0, 19)
    assert far == pytest.approx(_octile((10, 1), (hz, hx)))


# removing this lets the head sit beyond a dip that water could never climb out of
def test_farthest_source_never_crosses_a_dip():
    ctx = _valley_ctx()
    ctx["ymin"][:, 20] = 50.0
    (hz, hx), far = G.farthest_descending_source(ctx, [(10, 1)])
    assert hx == 19
    assert far == pytest.approx(_octile((10, 1), (hz, hx)))


# removing this lets the search walk across open sea to an unrelated coast
def test_farthest_source_does_not_cross_open_sea():
    ctx = _valley_ctx()
    ctx["open_sea"][:, 25] = True
    ctx["ymin"][:, 25] = 500.0                       # would be passable if sea were not blocked
    (hz, hx), _ = G.farthest_descending_source(ctx, [(10, 1)])
    assert hx <= 24


# ================================================================ coastal_systems


# removing this lets a river system's mouth catchment disagree with the cells that drain to it
def test_coastal_systems_mouth_catchment_counts_its_basin():
    ymin, sea = _v_valley()
    filled, order = D.priority_flood(ymin, sea, SEA)
    dirs = D.d8(filled, sea)
    acc = D.accumulation(dirs, order)
    dr = {"km2": acc, "dirs": dirs, "filled": filled, "burn": ymin, "order": order}
    systems = G.coastal_systems({"open_sea": sea, "ymin": ymin}, dr, min_km2=0)
    assert systems, "no system reaches the sea"
    assert sum(s["catchment_km2"] for s in systems) == int((~sea).sum())
    top = systems[0]
    assert top["catchment_km2"] == max(s["catchment_km2"] for s in systems)
    mz, mx = top["_cell"]
    assert sea[D.receiver(dirs, mz, mx)]
    hz, hx = top["_head_cell"]
    assert top["longest_descending_path_blocks"] > 0 and hz < mz


# ========================================================== rivers_from_landmarks


def _lm(lid, kind, axis, high, low, basis="hand carved"):
    return {"id": lid, "name": lid, "kind": kind,
            "axes": [{"id": "channel", "polyline": axis, "basis": basis}],
            "measured": {"high_end": {"x": high[0], "z": high[1], "bed": 90},
                         "low_end": {"x": low[0], "z": low[1], "bed": 80}}}


# removing this drops ravines from the plan, or lets rivers redrawn on graded courses become new sources
def test_rivers_from_landmarks_includes_ravines_and_treats_graded_axes_as_derived():
    open_sea = np.zeros((300, 300), bool)
    lms = [
        _lm("main", "river", [(0, 100), (600, 100)], (0, 100), (600, 100)),
        _lm("gully", "ravine", [(300, 600), (300, 150)], (300, 600), (300, 150)),
        _lm("redrawn", "river", [(900, 900), (1100, 900)], (900, 900), (1100, 900), basis="graded course x_outflow"),
        _lm("near_redrawn", "river", [(1000, 1100), (1000, 950)], (1000, 1100), (1000, 950)),
        _lm("hill", "mountain", [], (0, 0), (0, 0)),
    ]
    rivers = {r["id"]: r for r in G.rivers_from_landmarks(lms, [], open_sea)}
    assert set(rivers) == {"main", "gully", "redrawn", "near_redrawn"}
    assert rivers["gully"]["landmark_kind"] == "ravine"
    ends = {e["end"]: e for e in rivers["gully"]["ends"]}
    assert ends["low_end"]["at"] == "confluence" and ends["low_end"]["confluence_with"] == "main"
    assert ends["high_end"]["at"] == "inland"
    assert {e["at"] for e in rivers["redrawn"]["ends"]} == {"graded_source"}
    near = {e["end"]: e for e in rivers["near_redrawn"]["ends"]}
    assert near["low_end"]["at"] == "inland", "a redrawn course is not a confluence target"


# ============================================================ cut, end to end, by reach


N_CUT = 256
ROW = 100
GROUND = 120.0
PIT = (ROW, 20)
DRY = dict(_reach(width=6, bank=2.0), from_m=0, to_m=40, bed="GRAVEL", depth=3.0)
LAKE = dict(_reach(width=6, bank=2.0), from_m=40, to_m=160, water_body=True)
VALE = dict(_reach(width=16, bank=1.0, valley=VALLEY), from_m=160, to_m=240, depth=6.0)
POLY = [[4, ROW, 104.0, 101.0], [44, ROW, 102.0, 99.0], [164, ROW, 102.0, 99.0],
        [170, ROW, 100.0, 94.0], [244, ROW, 100.0, 94.0]]


def _write_png(path, heights):
    samples = F.to_samples(heights)
    return F.write_png(path, samples), samples


def _vale_world(tmp_path, derived=False):
    src = tmp_path / "src"
    h = np.full((N_CUT, N_CUT), GROUND)
    h[PIT] = 90.0
    base, samples = _write_png(src / "base.png", h)
    world = F.world_config(base, samples)
    base_sha = world["heightmap"]["sha256"]
    if derived:
        imported, _ = _write_png(src / "imported.png", np.full((N_CUT, N_CUT), 50.0))
        world["heightmap"] = dict(world["heightmap"], path=imported.name,
                                  sha256=hashlib.sha256(imported.read_bytes()).hexdigest(),
                                  derived_from={"path": base.name, "sha256": base_sha})
    wpath = tmp_path / "world.json"
    wpath.write_text(json.dumps(world), encoding="utf-8")
    return wpath, src, base, world, base_sha


def _vale_plan(tmp_path, sha):
    course = {"id": "vale", "valid": True, "graded_polyline": POLY,
              "graded_polyline_fields": ["x", "z", "surface_y", "floor_y"],
              "reaches": [DRY, LAKE, VALE]}
    p = tmp_path / "rivers.json"
    p.write_text(json.dumps({"schema": G.SCHEMA, "computed_from_sha256": sha, "courses": [course], "cut": None}),
                 encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def vale_cut(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("vale")
    wpath, src, base, world, sha = _vale_world(tmp)
    plan = _vale_plan(tmp, sha)
    out_dir = tmp / "out"
    out_dir.mkdir()
    rc = G.main(["cut", "--world", str(wpath), "--source-root", str(src), "--plan", str(plan),
                 "--out-name", "vale.png", "--out-dir", str(out_dir)])
    before = np.array(Image.open(base)).astype(np.int64)
    after = np.array(Image.open(out_dir / "vale.png")).astype(np.int64)
    return {"rc": rc, "src": src, "out_dir": out_dir, "world": world, "before": before, "after": after,
            "doc": json.loads(plan.read_text(encoding="utf-8")), "base": base, "sha": sha}


# removing this lets a per-reach cut raise a column or fill the pit it crosses
def test_reach_cut_only_lowers(vale_cut):
    assert vale_cut["rc"] == 0
    assert (vale_cut["after"] <= vale_cut["before"]).all()
    assert vale_cut["after"][PIT] == vale_cut["before"][PIT]


# removing this lets `cut` carve a channel through a lake the course crosses
def test_water_body_reach_is_not_carved(vale_cut):
    # dry banks reach ground within 3 + 19/2 + 3 blocks of x = 44; the valley within 59 of x = 165
    assert (vale_cut["after"][:, 60:105] == vale_cut["before"][:, 60:105]).all()


# removing this lets the carved centreline stand above the graded floor, so water has no bed to run in
def test_centreline_reaches_the_floor_outside_lakes(vale_cut):
    y = T.sample_to_height(vale_cut["after"], vale_cut["world"])
    pts, chain = G.densify_chained(POLY)
    checked = 0
    for (x, z, _s, floor), ch in zip(pts, chain):
        if G.at_chainage([DRY, LAKE, VALE], ch)["water_body"] or float(x) != int(x) or (z, x) == PIT:
            continue
        got = y[int(z), int(x)]
        assert got <= floor + 1e-9, (x, floor, got)
        # where the floor falls steeply (x 164..170: 5 blocks in 6) a downstream station's bed may go lower
        # at the centre; elsewhere the centre is the floor to within one sample
        if not 160 <= x <= 172:
            assert got >= floor - ONE_SAMPLE - 1e-9, (x, floor, got)
        checked += 1
    assert checked > 100
    check = vale_cut["doc"]["cut"]["check"]["courses"][0]
    assert check["thalweg_above_floor_max"] == 0 and check["floor_rise_max"] == 0


# removing this lets the major river's valley reach be cut as a plain channel, without floodplain or terraces
def test_valley_reach_cuts_floodplain_and_terraces(vale_cut):
    y = T.sample_to_height(vale_cut["after"], vale_cut["world"])
    x = 210
    for d in range(0, 70):
        want = min(GROUND, _profile_by_rule(float(d), 100.0, 94.0, VALE))
        for z in (ROW + d, ROW - d):
            assert want - ONE_SAMPLE - 1e-9 <= y[z, x] <= want + 1e-9, (d, want, y[z, x])
    col = y[ROW:ROW + 60, x]
    plain = np.flatnonzero(np.abs(col - 101.0) < 0.01)
    assert len(plain) >= VALLEY["floodplain_width"], "no floodplain one block above the water"
    assert (np.abs(col - 106.0) < 0.01).sum() >= 7 and (np.abs(col - 111.0) < 0.01).sum() >= 5


# removing this drops the per-course cost the plan uses to compare courses, or --out-dir
def test_cut_records_cost_by_course_and_honours_out_dir(vale_cut):
    cut = vale_cut["doc"]["cut"]
    assert (vale_cut["out_dir"] / "vale.png").is_file()
    assert not (vale_cut["src"] / "vale.png").exists()
    assert cut["output"]["sha256"] == hashlib.sha256((vale_cut["out_dir"] / "vale.png").read_bytes()).hexdigest()
    assert set(cut["cost_by_course"]) == {"vale"} == set(cut["courses_cut"])
    cost = cut["cost_by_course"]["vale"]
    assert cost["volume_blocks"] > 0
    assert cost["deepest_cut_blocks"] == pytest.approx(GROUND - 94.0, abs=0.1)
    assert 55 <= cost["widest_cut_half_width_blocks"] <= 62


# removing this lets `cut` run on the imported (already cut) file instead of the authored heightmap
def test_cut_uses_derived_from_as_its_base(tmp_path):
    wpath, src, base, world, base_sha = _vale_world(tmp_path, derived=True)
    plan = _vale_plan(tmp_path, base_sha)
    assert G.main(["cut", "--world", str(wpath), "--source-root", str(src), "--plan", str(plan),
                   "--out-name", "vale.png"]) == 0
    doc = json.loads(plan.read_text(encoding="utf-8"))
    assert doc["cut"]["from_heightmap"] == {"path": "base.png", "sha256": base_sha}
    out = np.array(Image.open(src / "vale.png")).astype(np.int64)
    before = np.array(Image.open(base)).astype(np.int64)
    assert (out <= before).all()
    assert (out[:, 60:105] == before[:, 60:105]).all(), "carved from the flat-50 import instead of the base"

    path, sha = G.base_heightmap(world, wpath, str(src))
    assert Path(path).name == "base.png" and sha == base_sha
    assert Path(G.base_heightmap(world, wpath, None, str(base))[0]) == base
    with pytest.raises(T.TerrainUnavailable):
        G.base_heightmap(world, wpath, None, str(src / "imported.png"))


# removing this lets a plan made on the imported file be cut as if it were made on the authored one
def test_cut_refuses_a_plan_computed_from_the_imported_file(tmp_path):
    wpath, src, base, world, base_sha = _vale_world(tmp_path, derived=True)
    plan = _vale_plan(tmp_path, world["heightmap"]["sha256"])
    with pytest.raises(SystemExit):
        G.main(["cut", "--world", str(wpath), "--source-root", str(src), "--plan", str(plan),
                "--out-name", "vale.png"])
    assert not (src / "vale.png").exists()


def test_base_heightmap_without_derived_from_is_the_heightmap(tmp_path):
    # removing this lets a world without a derived import plan rivers on the wrong file
    wpath, src, base, world, base_sha = _vale_world(tmp_path)
    path, sha = G.base_heightmap(world, wpath, str(src))
    assert Path(path) == base and sha == base_sha


# ===================================================================== paint_rivers


PN = 128
PAINT_SHA = "c" * 64
COLD_ID = PP.WP_BIOMES["minecraft:snowy_taiga"]
WARM_ID = PP.WP_BIOMES["minecraft:plains"]


def _paint_course(cid, z, surface0, surface1, reaches):
    return {"id": cid, "valid": True, "graded_polyline": [[8, z, surface0, surface0 - 3], [118, z, surface1, surface1 - 3]],
            "reaches": reaches}


P_REACHES = [dict(_reach(width=6), from_m=0, to_m=40, bed="GRAVEL"),
             dict(_reach(width=6), from_m=40, to_m=70, water_body=True),
             dict(_reach(width=8), from_m=70, to_m=110, bed="CLAY")]


def _paint_setup(tmp_path, monkeypatch, sha=PAINT_SHA, courses_cut=("flows",)):
    monkeypatch.setattr(PP, "N", PN)
    monkeypatch.setattr(PP, "ROOT", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "world.json").write_text(json.dumps({"heightmap": {"sha256": PAINT_SHA}}), encoding="utf-8")
    heights = np.full((PN, PN), 100.0, np.float32)
    heights[25:36, :] = 90.0                           # a carved trough along the "flows" row
    heights[30, 100:104] = 98.5                        # a hump in the channel, above the level there (98)
    heights[30, 30] = 120.0                            # a spike in the gravel reach's channel: never wet
    doc = {"schema": G.SCHEMA, "courses": [
        _paint_course("flows", 30, 99.7, 98.2, P_REACHES),
        _paint_course("uncut", 90, 99.0, 98.0, [dict(_reach(width=6), from_m=0, to_m=110)]),
    ], "cut": {"output": {"sha256": sha}, "courses_cut": list(courses_cut)}}
    rp = tmp_path / "rivers.json"
    rp.write_text(json.dumps(doc), encoding="utf-8")
    biome = np.full((PN, PN), WARM_ID, np.uint8)
    biome[:, 64:] = COLD_ID
    terr = np.full((PN, PN), PP.TERRAIN_CODES["GRASS"], np.uint8)
    trees = {k: np.ones((PN, PN), np.uint8) for k in PP.TREE_LAYERS}   # the "allowed" mask starts at 1
    plants = {k: np.ones((PN, PN), bool) for k in PP.PLANT_SETS}
    frost = np.ones((PN, PN), bool)
    out = tmp_path / "paint"
    out.mkdir(exist_ok=True)
    return rp, heights, biome, terr, trees, plants, frost, out, doc


def _paint_oracle(course, heights):
    """Nearest non-lake station within half width (first wins a tie) -> floor(surface) where ground is lower."""
    pts, chain = G.densify_chained(course["graded_polyline"])
    level = np.zeros((PN, PN), np.int64)
    bed = np.zeros((PN, PN), object)
    best = np.full((PN, PN), np.inf)
    zz, xx = np.mgrid[0:PN, 0:PN]
    for (x, z, s, _f), ch in zip(pts, chain):
        r = G.at_chainage(course["reaches"], ch)
        if r["water_body"]:
            continue
        d = np.hypot(xx - x, zz - z)
        take = (d <= r["width"] / 2.0) & (d < best)
        best[take] = d[take]
        level[take] = math.floor(s)
        bed[take] = r["bed"]
    wet = (level > 0) & (heights < level)
    return np.where(wet, level, 0), bed, wet


@pytest.fixture
def painted_rivers(tmp_path, monkeypatch):
    rp, heights, biome, terr, trees, plants, frost, out, doc = _paint_setup(tmp_path, monkeypatch)
    manifest = PP.paint_rivers(rp, heights, biome, terr, trees, plants, frost, out)
    return {"manifest": manifest, "heights": heights, "biome": biome, "terr": terr, "trees": trees,
            "plants": plants, "frost": frost, "out": out, "doc": doc}


# removing this lets the per-column water level crop disagree with the graded surface or flood dry ground
def test_level_crop_is_floor_of_surface_where_ground_is_lower(painted_rivers):
    man = painted_rivers["manifest"]
    assert [m["name"] for m in man] == ["flows"]
    m = man[0]
    img = Image.open(painted_rivers["out"] / m["levels"])
    assert img.mode == "L"
    crop = np.asarray(img).astype(np.int64)
    full = np.zeros((PN, PN), np.int64)
    full[m["z"]:m["z"] + crop.shape[0], m["x"]:m["x"] + crop.shape[1]] = crop
    want, _, wet = _paint_oracle(painted_rivers["doc"]["courses"][0], painted_rivers["heights"])
    assert np.array_equal(full, want)
    assert wet.any() and full[30, 30] == 0 and full[30, 29] == 99, "a spike above the level stays dry"
    assert full[30, 101] == 0 and full[30, 110] == 98, "a hump above the level there stays dry"
    # lake stations x 49..78; dry circles reach x <= 51 from above and x >= 75 from below
    assert (full[:, 52:75] == 0).all(), "a lake-only stretch gets no river water"
    assert m["columns"] == int(wet.sum())
    assert (m["min_level"], m["max_level"]) == (int(want[wet].min()), int(want[wet].max()))


# removing this lets paint.js receive a water entry it cannot read (it reads name, x, z and levels)
def test_river_manifest_entries_match_what_paint_js_reads(painted_rivers):
    js = (ROOT / "tools" / "worldpainter" / "paint.js").read_text(encoding="utf-8")
    for key in ("w.levels", "w.x", "w.z", "w.name"):
        assert key in js, key
    for m in painted_rivers["manifest"]:
        assert {"name", "x", "z", "levels"} <= set(m)
        assert "mask" not in m and "level" not in m, "a levels entry must not also look like a flat lake entry"
        assert isinstance(m["x"], int) and isinstance(m["z"], int)
        assert (painted_rivers["out"] / m["levels"]).is_file()


# removing this lets beds ignore their reach material, banks stay grass, or the river biome not be painted
def test_bed_banks_and_biome_follow_reaches(painted_rivers):
    course = painted_rivers["doc"]["courses"][0]
    want, bed, wet = _paint_oracle(course, painted_rivers["heights"])
    t, b = painted_rivers["terr"], painted_rivers["biome"]
    for z, x in zip(*np.nonzero(wet)):
        assert t[z, x] == PP.TERRAIN_CODES[bed[z, x]], (z, x, bed[z, x])
        expect = PP.WP_BIOMES["minecraft:frozen_river"] if x >= 64 else PP.WP_BIOMES["minecraft:river"]
        assert b[z, x] == expect, (z, x)
    # just outside the gravel reach's water: gravel bank; outside the clay reach's water: sand bank
    assert t[30 - 4, 20] == PP.TERRAIN_CODES["GRAVEL"]
    assert t[30 - 5, 100] == PP.TERRAIN_CODES["SAND"]
    assert b[30 - 5, 100] == PP.WP_BIOMES["minecraft:frozen_river"]
    assert t[5, 20] == PP.TERRAIN_CODES["GRASS"] and b[5, 20] == WARM_ID


# removing this lets trees stand in the river or on its banks, and snow sit on moving water
def test_trees_plants_and_frost_cleared_on_the_water(painted_rivers):
    _, _, wet = _paint_oracle(painted_rivers["doc"]["courses"][0], painted_rivers["heights"])
    assert list(painted_rivers["trees"]) == ["allowed"]
    for k, layer in painted_rivers["trees"].items():
        assert (layer[wet] == 0).all(), k
        assert layer[30 - 4, 20] == 0 and layer[30 - 5, 100] == 0, "a trunk may not stand on the bank either"
        assert layer[5, 5] == 1, "ground away from the river stays allowed"
    for k, layer in painted_rivers["plants"].items():
        assert not layer[wet].any(), k
    assert not painted_rivers["frost"][wet].any()
    assert painted_rivers["frost"][5, 5]


# removing this lets courses the cut skipped be painted with water they have no channel for
def test_courses_not_cut_are_not_painted(painted_rivers):
    assert not (painted_rivers["out"] / "river_uncut.png").exists()
    assert (painted_rivers["terr"][80:100, :] == PP.TERRAIN_CODES["GRASS"]).all()
    assert (painted_rivers["trees"]["allowed"][80:100, :] == 1).all()


# removing this lets river water be painted on a heightmap that does not have the channels cut into it
def test_paint_rivers_refuses_a_cut_that_is_not_the_imported_heightmap(tmp_path, monkeypatch):
    rp, heights, biome, terr, trees, plants, frost, out, _ = _paint_setup(tmp_path, monkeypatch, sha="d" * 64)
    before = terr.copy()
    with pytest.raises(SystemExit):
        PP.paint_rivers(rp, heights, biome, terr, trees, plants, frost, out)
    assert np.array_equal(terr, before)
    assert not list(out.glob("river_*.png"))


# removing this lets paint_rivers refuse the sculpted import (whose river channels the sculpt keeps) or paint rivers on
# a sculpt made from a different cut
def test_paint_rivers_accepts_the_cut_a_sculpt_was_made_from(tmp_path, monkeypatch):
    rp, heights, biome, terr, trees, plants, frost, out, _ = _paint_setup(tmp_path, monkeypatch)
    wp = tmp_path / "data" / "world.json"
    wp.write_text(json.dumps({"heightmap": {"sha256": "9" * 64, "sculpted_from": {"sha256": PAINT_SHA}}}),
                  encoding="utf-8")
    assert [m["name"] for m in PP.paint_rivers(rp, heights, biome, terr, trees, plants, frost, out)] == ["flows"]
    wp.write_text(json.dumps({"heightmap": {"sha256": PAINT_SHA, "sculpted_from": {"sha256": "9" * 64}}}),
                  encoding="utf-8")
    with pytest.raises(SystemExit):
        PP.paint_rivers(rp, heights, biome, terr, trees, plants, frost, out)


# ================================================================ validate_data rivers


BASE_SHA, CUT_SHA = "a" * 64, "b" * 64


def _rivers_ctx(tmp_path, world_hm, rivers_doc, landmarks=None):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / "world.json").write_text(json.dumps({"schema": "cobblers.world/1", "heightmap": world_hm,
                                              "vertical": {"sea_level": 62}}, indent=1), encoding="utf-8")
    (d / "rivers.json").write_text(json.dumps(dict({"schema": "cobblers.rivers/1"}, **rivers_doc), indent=1),
                                   encoding="utf-8")
    if landmarks is not None:
        (d / "landmarks.json").write_text(json.dumps({"schema": "cobblers.landmarks/1", "landmarks": landmarks},
                                                     indent=1), encoding="utf-8")
    ctx = V.Context(d, None, V.Report())
    V.check_schema(ctx)
    V.check_rivers(ctx)
    return ctx.report.findings


def _course_row(cid="c", poly=None, valid=True):
    return {"id": cid, "source": {"kind": "lake_outflow"}, "valid": valid, "verdict": "descends",
            "graded_polyline": poly if poly is not None else [[0, 0, 80.0, 77.0], [10, 0, 79.0, 76.0]]}


def _derived_doc(**kw):
    doc = {"computed_from_sha256": BASE_SHA, "courses": [_course_row()],
           "cut": {"from_heightmap": {"sha256": BASE_SHA}, "output": {"sha256": CUT_SHA}}}
    doc.update(kw)
    return doc


DERIVED_HM = {"sha256": CUT_SHA, "derived_from": {"path": "base.png", "sha256": BASE_SHA}}


def _river_findings(findings, severity=V.ERROR):
    return [f.message for f in findings if f.check == "rivers" and f.severity == severity]


# removing this lets a consistent derived import (plan on the base, cut is the import) be reported as broken
def test_check_rivers_accepts_a_consistent_derived_import(tmp_path):
    findings = _rivers_ctx(tmp_path, DERIVED_HM, _derived_doc())
    assert not [f for f in findings if f.check == "rivers" and f.severity in (V.ERROR, V.WARNING)]


# removing this lets rivers planned on the imported (cut) file pass, although they were meant for the base
def test_check_rivers_flags_a_plan_not_computed_from_derived_from(tmp_path):
    errs = _river_findings(_rivers_ctx(tmp_path, DERIVED_HM, _derived_doc(computed_from_sha256=CUT_SHA)))
    assert len(errs) == 1 and "computed from" in errs[0]


# removing this lets world.json import a heightmap that is not the recorded river cut
def test_check_rivers_flags_an_import_that_is_not_the_cut_output(tmp_path):
    doc = _derived_doc()
    doc["cut"]["output"]["sha256"] = "e" * 64
    errs = _river_findings(_rivers_ctx(tmp_path, DERIVED_HM, doc))
    assert len(errs) == 1 and "not the river cut" in errs[0]
    errs = _river_findings(_rivers_ctx(tmp_path, DERIVED_HM, _derived_doc(cut=None)))
    assert len(errs) == 1 and "not the river cut" in errs[0]


# removing this lets the cut-output rule fire on a world that imports the authored heightmap directly
def test_check_rivers_without_derived_from_compares_to_the_heightmap(tmp_path):
    hm = {"sha256": BASE_SHA}
    doc = _derived_doc()
    assert not _river_findings(_rivers_ctx(tmp_path, hm, doc))
    errs = _river_findings(_rivers_ctx(tmp_path, hm, _derived_doc(computed_from_sha256=CUT_SHA)))
    assert len(errs) == 1 and "computed from" in errs[0]


# ---------------------------------------------------------------- the major river's head: valley walls
#
# grade_rivers.walled_stations and valley_head run on synthetic heights below. plan() applies the head inline: it
# truncates the graded stations at the head, characterises the whole path (_trunk_full), drops the reaches above the
# head chainage and shifts the rest, and counts the removed upper path in the sizing drainage (_trunk_upper). That
# slicing lives inside plan(), which needs the whole planning context, so it is not unit-tested here: the validator
# checks what plan records in rivers.json instead.

WALL_N = 600
COURSE_Z = 300
SURFACE = 80.0


def _course(x0=20, x1=580, z=COURSE_Z):
    """A straight dense course along x, one station per block, water at SURFACE."""
    st = [(x, z, SURFACE - 3, -1) for x in range(x0, x1)]
    return st, [SURFACE] * len(st)


def _walls(north=True, south=True, rise=15.0, gap=100, x_from=0, x_to=WALL_N):
    """Ground at SURFACE everywhere, raised by `rise` beyond `gap` blocks from the course on the chosen sides."""
    h = np.full((WALL_N, WALL_N), SURFACE, np.float32)
    if north:
        h[:COURSE_Z - gap, x_from:x_to] += rise
    if south:
        h[COURSE_Z + gap + 1:, x_from:x_to] += rise
    return h


# removing this lets a trough with valley walls on both sides read as open ground, so the head never moves off the
# hillside onto the confined valley floor
def test_walled_stations_trough_with_two_walls_is_walled():
    st, surf = _course()
    rows = G.walled_stations(_walls(), st, surf)
    assert rows and all(len(r) == 5 for r in rows), "(chainage, x, z, walled, station index)"
    assert all(r[3] for r in rows)
    assert [r[0] for r in rows] == [G.WALL_STEP * k for k in range(len(rows))], "one sample every WALL_STEP blocks"
    assert (rows[0][1], rows[0][2]) == (20, COURSE_Z)
    assert all(st[r[4]][:2] == (r[1], r[2]) for r in rows), "each row's index is the station it sampled"


# removing this lets a hillside with ground rising on one side only count as a valley (the rule needs both sides)
@pytest.mark.parametrize("north,south", [(True, False), (False, True)])
def test_walled_stations_one_wall_is_not_walled(north, south):
    st, surf = _course()
    assert not any(r[3] for r in G.walled_stations(_walls(north=north, south=south), st, surf))


# removing this lets a wall just under WALL_RISE, or one beyond WALL_REACH, count (and a wall exactly at the rise, or
# inside the reach, fail to count)
@pytest.mark.parametrize("rise,gap,walled", [
    (G.WALL_RISE - 0.1, 100, False), (G.WALL_RISE, 100, True),
    (15.0, G.WALL_REACH + 2, False), (15.0, G.WALL_REACH - 12, True),
])
def test_walled_stations_rise_and_reach_thresholds(rise, gap, walled):
    st, surf = _course()
    rows = G.walled_stations(_walls(rise=rise, gap=gap), st, surf)
    assert rows and all(r[3] is walled for r in rows), (rise, gap, [r[3] for r in rows][:5])


# removing this lets the head start at the first walled sample (or a run of two) instead of the first of WALL_RUN
# consecutive walled samples, so a short confined gap on the hillside becomes the river's head
def test_valley_head_needs_consecutive_walled_samples():
    st, surf = _course()
    h = np.full((WALL_N, WALL_N), SURFACE, np.float32)
    gap = 100
    for x_from, x_to in ((100, 170), (300, WALL_N)):         # samples x 116 and 164 walled, then x 308 onward
        h[:COURSE_Z - gap, x_from:x_to] += 15
        h[COURSE_Z + gap + 1:, x_from:x_to] += 15
    i, d, rows = G.valley_head(h, st, surf)
    walled = [r[1] for r in rows if r[3]]
    assert walled[:2] == [116, 164] and 212 not in walled, "the fixture has a run of two before the real head"
    assert d == 288 and st[i][:2] == (308, COURSE_Z)
    assert G.WALL_RUN == 3


# removing this lets a course that never runs between walls report a head (and move it)
def test_valley_head_is_none_when_never_walled():
    st, surf = _course()
    i, d, rows = G.valley_head(_walls(north=False), st, surf)
    assert (i, d) == (None, None) and rows and not any(r[3] for r in rows)


# removing this lets valley_head return a station other than the one it sampled: the station after it where the
# chainage rounds up (a diagonal course), or index 1 for a course walled from its first station, which plan's
# `if i_head:` would treat as a move and cut one station off the trunk while recording 0 blocks moved
@pytest.mark.parametrize("case", ["walled_from_start", "diagonal"])
def test_valley_head_index_is_the_station_of_the_walled_sample(case):
    if case == "walled_from_start":
        st, surf = _course()
        h = _walls()
    else:
        n = 900
        zz, xx = np.mgrid[0:n, 0:n]
        across = (zz - xx) / np.sqrt(2)
        h = np.where((np.abs(across) > 100) & (xx + zz >= 500), SURFACE + 15, SURFACE).astype(np.float32)
        st = [(k, k, SURFACE - 3, -1) for k in range(20, 860)]
        surf = [SURFACE] * len(st)
    i, d, rows = G.valley_head(h, st, surf)
    first = next(r for k, r in enumerate(rows) if all(q[3] for q in rows[k:k + G.WALL_RUN]))
    assert st[i][:2] == (first[1], first[2]), (case, i, st[i][:2], first)
    assert (i, d) == (first[4], first[0])
    if case == "walled_from_start":
        assert (i, d) == (0, 0), "a head at the first station is index 0 at chainage 0: no move, nothing cut"
    else:
        assert i > 0 and d > 0


# ---------------------------------------------------------------- validate_data: the recorded head rule

WALLS = {"wall_rise_blocks": 10.0, "wall_reach_blocks": 250, "consecutive_stations": 3, "station_spacing_blocks": 48}


def _head_doc(**rule):
    trunk = _course_row("major_river_trunk", poly=[[3136, 1636, 104.12, 101.32], [3162, 1662, 102.53, 99.73]])
    trunk.update(river="major_river", source={"kind": "system_head", "x": 3136, "z": 1636},
                 reaches=[{"from_m": 0, "to_m": 65, "catchment_km2": 1.037}])
    shrews = _course_row("shrews", poly=[[100, 100, 90.0, 87.0], [110, 100, 89.0, 86.0]])
    shrews["source"] = {"kind": "inland_end"}
    outflow = _course_row("lake_outflow", poly=[[200, 100, 90.0, 87.0], [210, 100, 89.0, 86.0]])
    outflow["source"] = {"kind": "lake_outflow"}
    head_rule = dict(WALLS, rule="valley_walls", path_head={"x": 2504, "z": 1444, "ground_y": 170.9},
                     moved_blocks_along_path=817)
    head_rule.update(rule)
    survey = [{"course": "shrews", "source_kind": "inland_end", "walled_from_start": True,
               "rule_would_move_head_blocks": 0, "walled_samples": 24, "samples": 38}]
    return _derived_doc(parameters={"grid_blocks": 4, "valley_head": {"wall_rise": 10.0, "wall_reach": 250, "run": 3,
                                                                      "step": 48}},
                        courses=[trunk, shrews, outflow],
                        major_river={"courses": ["major_river_trunk"], "head_rule": head_rule,
                                     "head_rule_survey_other_courses": survey})


def _head_errors(tmp_path, doc, severity=V.ERROR):
    return _river_findings(_rivers_ctx(tmp_path, DERIVED_HM, doc), severity)


# removing this lets every head-rule breaking case below pass on a fixture that was already failing
def test_head_rule_baseline_passes(tmp_path):
    findings = _rivers_ctx(tmp_path, DERIVED_HM, _head_doc())
    assert _river_findings(findings) == [] and _river_findings(findings, V.WARNING) == []


# removing this lets the fixture's wall values drift from tools/grade_rivers.py, so the cases below test other numbers
def test_head_rule_fixture_values_are_the_codes():
    code = ROOT / "tools" / "grade_rivers.py"
    assert {k: V._module_constant(code, c) for k, (c, _) in V.HEAD_RULE_CONSTANTS.items()} == WALLS
    assert (G.WALL_RISE, G.WALL_REACH, G.WALL_RUN, G.WALL_STEP) == (10.0, 250, 3, 48)


# removing this lets the real plan lose its head rule, record other wall values than the code's, or start the trunk
# somewhere other than its first graded station
def test_real_rivers_head_rule_passes():
    ctx = V.Context(ROOT / "data", None, V.Report())
    V.check_schema(ctx)
    V.check_rivers(ctx)
    bad = [f.message for f in ctx.report.findings if f.check == "rivers" and f.severity in (V.ERROR, V.WARNING)]
    assert bad == []


# removing this lets a plan record a head it did not choose by the valley-wall rule, with other wall values than the
# code's or the plan parameters', a negative move, a trunk source off its first station, or a malformed survey
@pytest.mark.parametrize("change,needle", [
    (lambda d: d["major_river"].pop("head_rule"), "head_rule is missing"),
    (lambda d: d["major_river"]["head_rule"].update(rule="catchment"), 'is \'catchment\', not "valley_walls"'),
    (lambda d: d["major_river"]["head_rule"].update(wall_rise_blocks=12.0), "wall_rise_blocks 12.0 is not tools/grade_rivers.py WALL_RISE 10.0"),
    (lambda d: d["major_river"]["head_rule"].update(wall_reach_blocks=200), "wall_reach_blocks 200 is not tools/grade_rivers.py WALL_REACH 250"),
    (lambda d: d["major_river"]["head_rule"].update(consecutive_stations=2), "consecutive_stations 2 is not tools/grade_rivers.py WALL_RUN 3"),
    (lambda d: d["major_river"]["head_rule"].update(station_spacing_blocks=64), "station_spacing_blocks 64 is not tools/grade_rivers.py WALL_STEP 48"),
    (lambda d: d["major_river"]["head_rule"].pop("wall_reach_blocks"), "wall_reach_blocks must be a number > 0"),
    (lambda d: d["parameters"]["valley_head"].update(run=4), "is not parameters.valley_head.run 4"),
    (lambda d: d["parameters"].pop("valley_head"), "parameters.valley_head is missing"),
    (lambda d: d["major_river"]["head_rule"].update(moved_blocks_along_path=-48), "moved_blocks_along_path must be a number >= 0"),
    (lambda d: d["major_river"]["head_rule"].pop("path_head"), "path_head needs x and z"),
    (lambda d: d["courses"][0]["source"].update(x=3140), "is not its first graded station (3136, 1636)"),
    (lambda d: d["courses"][0].update(source={"kind": "system_head", "x": 2504, "z": 1444}), "is not its first graded station"),
    (lambda d: d["major_river"].update(courses=["nowhere"]), "does not name a trunk course"),
    (lambda d: d["major_river"]["head_rule_survey_other_courses"][0].update(course="ghost"), "names course 'ghost', which is not in courses"),
    (lambda d: d["major_river"]["head_rule_survey_other_courses"][0].update(course="major_river_trunk"), "surveys the trunk itself"),
    (lambda d: d["major_river"]["head_rule_survey_other_courses"][0].update(course="lake_outflow"), "a lake outflow"),
    (lambda d: d["major_river"]["head_rule_survey_other_courses"].append(dict(d["major_river"]["head_rule_survey_other_courses"][0])), 'lists "shrews" twice'),
    (lambda d: d["major_river"]["head_rule_survey_other_courses"][0].update(walled_samples=40), "needs integer samples >= walled_samples"),
    (lambda d: d["major_river"]["head_rule_survey_other_courses"][0].update(walled_from_start="yes"), "walled_from_start must be true or false"),
    (lambda d: d["major_river"]["head_rule_survey_other_courses"][0].update(rule_would_move_head_blocks=96), "walled from its start but the rule would move its head 96"),
    (lambda d: d["major_river"]["head_rule_survey_other_courses"][0].update(rule_would_move_head_blocks=-1), "rule_would_move_head_blocks must be null or a number >= 0"),
])
def test_head_rule_breaks_are_errors(tmp_path, change, needle):
    doc = _head_doc()
    change(doc)
    errs = _head_errors(tmp_path, doc)
    assert any(needle in e for e in errs), errs


# removing this lets a trunk source a few blocks off its first station, inside the same grid cell (the head is chosen
# on the 4-block routing grid), be reported as broken
def test_head_rule_source_within_one_grid_cell_passes(tmp_path):
    doc = _head_doc()
    doc["courses"][0]["source"].update(x=3139, z=1633)
    assert _head_errors(tmp_path, doc) == []


# removing this lets a plan that found no walled stretch pass silently (it keeps the path head): it is a warning
def test_head_rule_without_a_walled_stretch_warns(tmp_path):
    doc = _head_doc(moved_blocks_along_path=None)
    assert _head_errors(tmp_path, doc) == []
    assert any("found no walled stretch" in w for w in _head_errors(tmp_path, doc, V.WARNING))


# removing this lets rivers.json keep wall values the code no longer uses (plan not rerun after a constant changed)
def test_head_rule_values_must_match_the_code_constants(tmp_path, monkeypatch):
    code = tmp_path / "grade_rivers.py"
    code.write_text("FACTOR = 4\nWALL_RISE = 12.0\nWALL_REACH = 250\nWALL_RUN = 3\nWALL_STEP = 48\n", encoding="utf-8")
    monkeypatch.setattr(V, "GRADE_RIVERS", code)
    errs = _head_errors(tmp_path, _head_doc())
    assert errs == ["major_river.head_rule.wall_rise_blocks 10.0 is not tools/grade_rivers.py WALL_RISE 12.0; rerun "
                    "tools/grade_rivers.py plan"], errs


# removing this lets a plan without a major river be reported as breaking the head rule
def test_no_major_river_no_head_rule_findings(tmp_path):
    assert _river_findings(_rivers_ctx(tmp_path, DERIVED_HM, _derived_doc())) == []


SCULPT_SHA = "d" * 64
SCULPTED_HM = {"sha256": SCULPT_SHA, "derived_from": {"path": "base.png", "sha256": BASE_SHA},
               "sculpted_from": {"path": "cut.png", "sha256": CUT_SHA}}


# removing this lets the validator reject the sculpt chain (authored -> river cut -> sculpt -> import) that
# paint_maps accepts, or accept a sculpt made from something other than the recorded cut
def test_check_rivers_follows_the_sculpt_chain(tmp_path):
    assert not _river_findings(_rivers_ctx(tmp_path, SCULPTED_HM, _derived_doc()))
    stale = dict(SCULPTED_HM, sculpted_from={"path": "cut.png", "sha256": "e" * 64})
    errs = _river_findings(_rivers_ctx(tmp_path, stale, _derived_doc()))
    assert len(errs) == 1 and "sculpted_from" in errs[0] and "not the river cut" in errs[0]


# removing this lets a sculpted world pass when the cut output is the imported (sculpted) file itself, which would
# mean the sculpt input and the cut disagree
def test_check_rivers_with_a_sculpt_does_not_accept_the_import_as_the_cut(tmp_path):
    doc = _derived_doc()
    doc["cut"]["output"]["sha256"] = SCULPT_SHA
    errs = _river_findings(_rivers_ctx(tmp_path, SCULPTED_HM, doc))
    assert len(errs) == 1 and "sculpted_from" in errs[0]
    broken = dict(SCULPTED_HM, sculpted_from={"path": "cut.png"})
    assert len(_river_findings(_rivers_ctx(tmp_path, broken, _derived_doc()))) == 1


# removing this lets a stored course that rises, or whose water is under the sea, pass validation
@pytest.mark.parametrize("poly,needle", [
    ([[0, 0, 80.0, 77.0], [10, 0, 80.5, 76.0]], "rises"),
    ([[0, 0, 80.0, 77.0], [10, 0, 79.0, 78.0]], "rises"),
    ([[0, 0, 63.0, 60.0], [10, 0, 61.0, 58.0]], "below sea level"),
])
def test_check_rivers_flags_rising_or_sub_sea_courses(tmp_path, poly, needle):
    errs = _river_findings(_rivers_ctx(tmp_path, DERIVED_HM, _derived_doc(courses=[_course_row(poly=poly)])))
    assert len(errs) == 1 and needle in errs[0]


def test_check_rivers_flags_polylines_on_invalid_courses_and_missing_ones_on_valid(tmp_path):
    # removing this lets an invalid course keep a polyline `cut` might carve, or a valid one have none
    courses = [_course_row("bad", valid=False), _course_row("empty", poly=[])]
    errs = _river_findings(_rivers_ctx(tmp_path, DERIVED_HM, _derived_doc(courses=courses)))
    assert len(errs) == 2
    assert any('"bad" is not valid' in e for e in errs) and any('"empty" has no graded polyline' in e for e in errs)


def test_check_rivers_warns_when_the_cut_came_from_another_heightmap(tmp_path):
    # removing this hides a cut made from a stale base
    doc = _derived_doc()
    doc["cut"]["from_heightmap"]["sha256"] = "f" * 64
    findings = _rivers_ctx(tmp_path, DERIVED_HM, doc)
    assert len(_river_findings(findings, V.WARNING)) == 1


def test_landmark_kind_ravine_is_accepted_and_unknown_kinds_are_not(tmp_path):
    # removing this lets the validator reject the ravine landmarks the planner and painter now use
    def lm(i, kind):
        return {"id": i, "name": i, "kind": kind, "anchor": {"x": 0, "z": 0}, "status": "built"}
    findings = _rivers_ctx(tmp_path, DERIVED_HM, _derived_doc(), landmarks=[lm("r", "ravine"), lm("g", "gorge")])
    errs = [f.message for f in findings if f.check == "schema" and f.severity == V.ERROR]
    assert len(errs) == 1 and '"g"' in errs[0] and "gorge" in errs[0]


# ==================================================================== region_measure


# removing this lets region area, bounds or elevation percentiles be re-measured on the wrong cells
def test_region_measure_on_a_synthetic_mask():
    n = 16
    y = np.tile(np.arange(n, dtype=np.float64) * 10.0, (n, 1))      # rises 10 per cell eastward
    slope = np.zeros((n, n))
    slope[:, 8:] = 10.0
    mask = np.zeros((n, n), bool)
    mask[2:6, 4:12] = True                                         # 4 rows x 8 columns
    m = RM.measure(mask, y, slope)
    assert m["area_km2"] == round(32 * RM.F * RM.F / 1e6, 3)
    assert m["bounds"] == {"min_x": 4 * RM.F, "min_z": 2 * RM.F, "max_x": 12 * RM.F - 1, "max_z": 6 * RM.F - 1}
    vals = np.repeat(np.arange(4, 12) * 10.0, 4)
    assert m["elevation"]["median"] == round(float(np.median(vals)), 1)
    assert m["elevation"]["p10"] == round(float(np.percentile(vals, 10)), 1)
    assert m["elevation"]["max"] == 110.0
    assert m["slope_degrees"]["mean"] == 5.0
    assert m["slope_degrees"]["flat_under_5_pct"] == 50.0


def test_region_measure_grids_and_mask_follow_eight_block_cells():
    # removing this lets polygons in block coordinates rasterise onto the wrong cells, or slope use the wrong spacing
    n = 64
    z, x = np.mgrid[0:n, 0:n].astype(np.float64)
    heights = 100.0 + x                                            # one block up per block east: 45 degrees
    y, slope = RM.grids(heights)
    assert y.shape == (n // RM.F, n // RM.F)
    assert np.allclose(slope, 45.0)
    mask = RM.mask_of([[[16, 16], [40, 16], [40, 40], [16, 40]], [[0, 0], [1, 1]]], y.shape[0])
    assert mask[2, 2] and mask[5, 5] and not mask[0, 0] and not mask[7, 7]
    d = RM.diff({"area_km2": 1.0, "elevation": {"median": 50.0}}, RM.measure(mask, y, slope))
    assert "area_km2" in d and "elevation.median" in d
