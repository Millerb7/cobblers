"""tools/foliage.py place(): the placement rules, on a synthetic 512x512 world with a tiny library dict.

Layout (x, z blocks):
  sub-region a  x 64..319,  z 64..447   type "dense" (via preset_defaults): 2x2 "big" and 1x1 "small" classes,
                                         lone trees "lone_a", debris "rock"
  sub-region b  x 320..447, z 64..255   type "other" (via assign): a closed forest
  sub-region c  x 320..447, z 256..447  type "meadow": an open type
  everything else                        no type
The allowed mask is cleared on lines x % 9 == 4 and z % 9 == 4, so an object whose origin column is allowed can
still reach a forbidden column within its ground_radius square. "big" has two variants (ground_radius 1 and 2) so
the group's radius is the larger. A settlement exclusion square and three landmark trees (one on the map, two off)
complete the fixture.

Not covered: whether the densities read as the intended forest in game, understory and floor painting (in
tools/paint_maps.py), and the water clearance at block scale, which lives in tools/paint_maps.py paint_foliage
(tests/test_paint_maps.py test_objects_keep_water_clearance_blocks_from_water). place() on its own only zeroes
density in 4-block cells whose sampled column is water; callers must clear allowed near water, as paint_maps does.
Whether WorldPainter's rotation really pivots on the origin column is not checked here.
"""
import copy
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import foliage as F  # noqa: E402

N = 512
G = F.G
EXCL = (150, 300, 190, 340)                  # x0, z0, x1, z1 inclusive
GIANT, GLADE = (200, 150), 20
SP = {"big": 12, "small": 4, "lone_a": 6, "other_tree": 6, "meadow_tree": 10}   # lone_a: sp_of.get(g, 6)

DOC = {
    "density_model": {"noise": {"ragged_scale": 96, "glade_scale": 320, "clump_scale": 72},
                      "water_clearance_blocks": 3, "settlement_clearance_blocks": 0},
    "types": {
        "dense": {
            "stems_per_ha": 400, "edge_width": 16, "ragged": 0, "glade_share": 0, "clumping": 0,
            "slope_lo": 20, "slope_hi": 34,
            # listed small first, so only the spacing sort can put big first
            "classes": [{"group": "small", "core": 1, "edge": 1, "spacing": SP["small"]},
                        {"group": "big", "core": 1, "edge": 0.5, "spacing": SP["big"]}],
            "lone": {"per_ha": 60, "reach": 64, "groups": ["lone_a"]},
            "debris": [{"group": "rock", "per_ha": 40, "zone": "any", "max_slope": 20}],
        },
        # ragged, so noise could push density past the sub-region if nothing zeroed it outside
        "other": {"stems_per_ha": 300, "edge_width": 8, "ragged": 24,
                  "classes": [{"group": "other_tree", "spacing": SP["other_tree"]}]},
        "meadow": {"stems_per_ha": 40, "edge_width": 0, "open": True,
                   "classes": [{"group": "meadow_tree", "spacing": SP["meadow_tree"]}]},
    },
    "preset_defaults": {"pa": "dense", "pc": "meadow", "pb": "dense"},
    "assign": {"b": {"type": "other"}},
    "landmark_trees": [
        {"id": "giant", "object": "landmark", "site": list(GIANT), "glade_radius": GLADE},
        {"id": "west_giant", "object": "landmark", "site": [-50, 100], "glade_radius": 20},
        {"id": "north_east_giant", "object": "landmark", "site": [600, 10], "glade_radius": 20},
    ],
}


def _lib_row(group, fp=1, height=10, crown=3.0, ground=0, name=None):
    return {"name": name or group + "_01", "group": group, "height": height, "crown_radius": crown,
            "trunk_footprint": fp, "eye_width": 1, "ground_radius": ground}


LIBRARY = {"objects": [_lib_row("big", fp=4, height=30, crown=6.0, ground=1),
                       _lib_row("big", fp=4, height=34, crown=6.0, ground=2, name="big_02"),
                       _lib_row("small"), _lib_row("lone_a"),
                       _lib_row("other_tree"), _lib_row("meadow_tree"), _lib_row("rock", height=2, crown=1.0, ground=2),
                       _lib_row("landmark", fp=9, height=40, crown=12.0, ground=5)]}
GROUND = {"big": 2, "small": 0, "lone_a": 0, "other_tree": 0, "meadow_tree": 0, "rock": 2}
SUBS = [{"id": "a", "paint": {"preset": "pa"}}, {"id": "b", "paint": {"preset": "pb"}},
        {"id": "c", "paint": {"preset": "pc"}}]
PRESETS = {"pa": {}, "pb": {}, "pc": {}}


def _world():
    heights = np.full((N, N), 80.0, np.float32)
    slope = np.zeros((N, N), np.float32)
    idx = np.zeros((N, N), np.uint8)
    idx[64:448, 64:320] = 1
    idx[64:256, 320:448] = 2
    idx[256:448, 320:448] = 3
    x = np.arange(N)
    allowed = np.ones((N, N), bool)
    allowed[:, x % 9 == 4] = False
    allowed[x % 9 == 4, :] = False
    excl = np.zeros((N, N), bool)
    excl[EXCL[1]:EXCL[3] + 1, EXCL[0]:EXCL[2] + 1] = True
    return dict(heights=heights, slope=slope, idx=idx, allowed=allowed, excl=excl,
                lake_depth=np.zeros((N, N), np.float32), water=np.zeros((N, N), bool))


def _place(doc=DOC, seed=11, world=None):
    w = world or _world()
    return F.place(doc, LIBRARY, SUBS, PRESETS, w["idx"], w["heights"], w["slope"], w["allowed"], w["lake_depth"],
                   w["water"], w["excl"], seed), w


@pytest.fixture(scope="module")
def placed():
    return _place()


def _xz(res, group):
    a = np.array(res["positions"].get(group, []), dtype=np.int64).reshape(-1, 2)
    return a[:, 0], a[:, 1]


# removing this lets every rule test below pass vacuously on a fixture that placed next to nothing
def test_fixture_places_every_kind_of_object(placed):
    res, _ = placed
    counts = {g: len(v) for g, v in res["positions"].items()}
    for g, least in (("big", 40), ("small", 100), ("lone_a", 5), ("other_tree", 50), ("meadow_tree", 5),
                     ("rock", 10), ("landmark", 1)):
        assert counts.get(g, 0) >= least, (g, counts)


def _square_ok(mask, x, z, r):
    """The (2r+1) square around (x, z) is on the map and mask is True over all of it."""
    return 0 <= x - r and x + r < N and 0 <= z - r and z + r < N and bool(mask[z - r:z + r + 1, x - r:x + r + 1].all())


# removing this lets an object's ground contact rest on a forbidden column under some rotation about its origin: the
# whole square of the group's ground_radius (largest over its variants) must be allowed
def test_ground_contact_square_only_on_allowed_columns(placed):
    res, w = placed
    allowed = w["allowed"]
    for g, r in GROUND.items():
        pts = res["positions"].get(g, [])
        bad = [(x, z) for x, z in pts if not _square_ok(allowed, x, z, r)]
        assert not bad, (g, r, bad[:5])
    # teeth: with forbidden lines at x % 9 == 4, a radius-2 square fits only where x % 9 is 7, 8, 0 or 1, while a
    # 1x1 or corner-anchored 2x2 check would also accept 2, 3, 5 and 6
    xs, zs = _xz(res, "big")
    assert len(xs) and set((xs % 9).tolist()) <= {7, 8, 0, 1} and set((zs % 9).tolist()) <= {7, 8, 0, 1}


# removing this lets trees, lone trees or debris reach into a settlement exclusion with any column of their ground
# contact square
def test_nothing_inside_exclusions(placed):
    res, w = placed
    x0, z0, x1, z1 = EXCL
    for g, r in GROUND.items():
        xs, zs = _xz(res, g)
        hit = (xs + r >= x0) & (xs - r <= x1) & (zs + r >= z0) & (zs - r <= z1)
        assert not hit.any(), (g, r)
    # the exclusion lies inside forest a, so an empty square is the rule working, not an empty forest
    near = [(x, z) for x, z in res["positions"]["small"] if x0 - 20 <= x <= x1 + 20 and z0 - 20 <= z <= z1 + 20]
    assert near


def _min_ratio(a_xy, a_sp, b_xy, b_sp, same):
    """Smallest distance / required distance over all pairs (chunked)."""
    worst = math.inf
    for i in range(0, len(a_xy), 400):
        d = np.hypot(a_xy[i:i + 400, None, 0] - b_xy[None, :, 0], a_xy[i:i + 400, None, 1] - b_xy[None, :, 1])
        need = (a_sp[i:i + 400, None] + b_sp[None, :]) / 2.0
        if same:
            rows = np.arange(i, min(i + 400, len(a_xy)))
            d[rows - i, rows] = np.inf
        worst = min(worst, float((d / need).min()))
    return worst


# removing this lets a stem crowd another inside (spacing_a + spacing_b) / 2, within a type or across types
def test_stems_keep_pairwise_spacing(placed):
    res, _ = placed
    pts, sps = [], []
    for g, sp in SP.items():
        for p in res["positions"].get(g, []):
            pts.append(p)
            sps.append(sp)
    xy, sp = np.array(pts, float), np.array(sps, float)
    assert _min_ratio(xy, sp, xy, sp, same=True) >= 1.0
    rocks = np.array(res["positions"]["rock"], float)
    # debris keeps (2.5 + spacing) / 2 from every stem and 3 blocks from other debris
    assert _min_ratio(rocks, np.full(len(rocks), 2.5), xy, sp, same=False) >= 1.0
    assert _min_ratio(rocks, np.full(len(rocks), 3.0), rocks, np.full(len(rocks), 3.0), same=True) >= 1.0


# removing this lets trees, lone trees or debris grow inside a landmark tree's glade
def test_landmark_glade_holds_only_the_landmark(placed):
    res, _ = placed
    assert res["positions"]["landmark"] == [GIANT]
    for g, pts in res["positions"].items():
        if g == "landmark":
            continue
        for x, z in pts:
            assert (x - GIANT[0]) ** 2 + (z - GIANT[1]) ** 2 >= GLADE ** 2, (g, x, z)


# removing this lets a landmark tree sited off the map crash placement or vanish without being reported
def test_landmark_trees_outside_the_map_are_skipped_and_listed(placed):
    res, _ = placed
    assert res["stats"]["_landmark_trees_outside_map"] == ["west_giant", "north_east_giant"]
    assert all(0 <= x < N and 0 <= z < N for pts in res["positions"].values() for x, z in pts)


# removing this lets small trees be accepted before big ones, so they fill the ground big trees need
def test_big_spacing_classes_are_accepted_first(monkeypatch):
    log = []

    class Logged(F.Spacing):
        def add(self, x, z, sp):
            log.append((id(self), sp))
            super().add(x, z, sp)

    monkeypatch.setattr(F, "Spacing", Logged)
    doc = copy.deepcopy(DOC)
    doc["types"] = {"dense": doc["types"]["dense"]}
    del doc["types"]["dense"]["lone"], doc["types"]["dense"]["debris"]
    doc["assign"] = {}
    doc["preset_defaults"] = {"pa": "dense"}
    doc["landmark_trees"] = []
    _place(doc)
    stems = [sp for owner, sp in log if owner == log[0][0]]
    assert set(stems) == {SP["big"], SP["small"]}
    assert stems == sorted(stems, reverse=True), "every big stem is accepted before the first small one"


# removing this lets a type's classes grow outside its own sub-regions, or give a closed forest's cells density
def test_class_stems_stay_inside_their_types_subregions(placed):
    res, w = placed
    idx4 = w["idx"][::G, ::G]
    for g, want in (("big", 1), ("small", 1), ("other_tree", 2), ("meadow_tree", 3)):
        xs, zs = _xz(res, g)
        assert (idx4[zs // G, xs // G] == want).all(), g
    for t, want in (("dense", 1), ("other", 2), ("meadow", 3)):
        f = res["fields"][t]
        z0, z1, x0, x1 = f["box"]
        assert f["density"].shape == (z1 - z0, x1 - x0)
        outside = idx4[z0:z1, x0:x1] != want
        assert outside.any() and (f["density"][outside] == 0).all(), t


# removing this lets lone trees fall inside their own forest or into a neighbouring closed forest (only open ground:
# no type, or an open type)
def test_lone_trees_only_into_open_ground(placed):
    res, w = placed
    idx4 = w["idx"][::G, ::G]
    xs, zs = _xz(res, "lone_a")
    closed = np.zeros(idx4.shape, bool)
    for t in ("dense", "other"):
        f = res["fields"][t]
        z0, z1, x0, x1 = f["box"]
        closed[z0:z1, x0:x1] |= f["inside"]
    assert not closed[zs // G, xs // G].any(), "no lone tree inside a closed forest (its own or a neighbour's)"
    cells = idx4[zs // G, xs // G]
    assert (cells == 3).any() and (cells == 0).any(), "lone trees reach both an open type and untyped ground"
    # within reach of forest a: nothing past 64 blocks from its edge (x 64..319, z 64..447)
    dx = np.maximum(np.maximum(64 - xs, xs - 319), 0)
    dz = np.maximum(np.maximum(64 - zs, zs - 447), 0)
    assert (np.hypot(dx, dz) <= 64 + G * 2).all()


# removing this lets the same seed paint a different forest on every run (or a new seed repaint the same one)
def test_placement_is_deterministic_per_seed():
    a, _ = _place(seed=5)
    b, _ = _place(seed=5)
    c, _ = _place(seed=6)
    assert a["positions"] == b["positions"] and np.array_equal(a["canopy"], b["canopy"])
    assert a["stats"] == b["stats"]
    assert a["positions"] != c["positions"]


# removing this lets the canopy grid omit a tree's crown, so sightline checks see through planned forest
def test_canopy_carries_crown_tops_over_ground(placed):
    res, w = placed
    canopy = res["canopy"]
    assert canopy.shape == (N // G, N // G)
    x, z = res["positions"]["big"][0]
    assert canopy[z // G, x // G] >= 80 + 30
    assert canopy[GIANT[1] // G, GIANT[0] // G] == 80 + 40
    assert (canopy[:, : 16 // G] == 0).all(), "no trees along the empty western margin"


# removing this lets a group's placement radius come from one variant (or an average), so a wider variant chosen by
# WorldPainter spills past the checked square
def test_group_ground_radius_is_the_largest_variant():
    gs = F.group_stats(LIBRARY)
    assert gs["big"]["ground_radius"] == 2 and gs["rock"]["ground_radius"] == 2 and gs["small"]["ground_radius"] == 0
    reordered = {"objects": list(reversed(LIBRARY["objects"]))}
    assert F.group_stats(reordered)["big"]["ground_radius"] == 2, "not just the first or last variant"


# removing this lets an object whose ground contact square leaves the map be placed at the edge (the array slice
# silently shrinks, so the out-of-map columns are never checked)
def test_ground_contact_square_must_stay_on_the_map():
    w = _world()
    w["allowed"][:] = True
    w["excl"][:] = False
    w["idx"][:] = 1                                 # forest a covers the whole map
    doc = copy.deepcopy(DOC)
    doc["types"]["dense"].update(edge_width=0, stems_per_ha=2000)
    doc["types"]["dense"].pop("lone")
    doc["landmark_trees"] = []
    lib = copy.deepcopy(LIBRARY)
    for r in lib["objects"]:
        if r["group"] == "small":
            r["ground_radius"] = 6
    res = F.place(doc, lib, SUBS, PRESETS, w["idx"], w["heights"], w["slope"], w["allowed"], w["lake_depth"],
                  w["water"], w["excl"], 3)
    xs, zs = _xz(res, "small")
    assert len(xs) > 200
    assert xs.min() >= 6 and zs.min() >= 6 and xs.max() <= N - 7 and zs.max() <= N - 7
