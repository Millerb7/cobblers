"""tools/sculpt.py: sampling helpers, the raw 16-bit write-back, coast profiles, protection, volcano forms, and
run() on a small synthetic island; plus tools/coast_measure.py profile_metrics.

Everything runs on synthetic arrays and tmp fixture worlds. main apply runs once with ROOT monkeypatched to a tmp
directory and run() replaced by a stub, so only the read, sha check and write-back path is exercised; the real
source files, build/ and derived/ are never touched. Coast class specs are fixture values shaped like
data/sculpt.json, not the real ones.

Not covered: whether the sculpted coasts, massifs and cones look right in game or in WorldPainter, classify_coast's
class decisions on real geography, sculpt_massif (summits, strata), class_weights blending across stretches, and
tools/massif_measure.py.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import coast_measure as CM  # noqa: E402
import sculpt as S  # noqa: E402
import terrain as T  # noqa: E402

SEA = 62.0
IMPORT = {"input_units": "fraction_of_full_scale", "low_in": 0.0, "high_in": 0.996078431, "low_out": 10.093458,
          "high_out": 200, "water_level": 62, "clamp_low": True, "clamp_high": True}
WORLD = {"heightmap": {"bit_depth": 16}, "vertical": {"sea_level": 62}, "import": IMPORT}


# ------------------------------------------------------------------ sampling and raw values

# removing this lets bilinear clamp x to the row count on a non-square array, so a massif or volcano crop wider than
# it is tall samples the wrong columns
def test_bilinear_on_a_non_square_array():
    zz, xx = np.mgrid[0:4, 0:10].astype(np.float32)
    h = 10 * zz + xx
    xs = np.array([7.5, 8.25, 9.0, 0.0])
    zs = np.array([1.0, 2.5, 3.0, 0.0])
    assert np.allclose(S.bilinear(h, xs, zs), 10 * zs + xs)


# removing this lets the coarse-grid upsample shift by half a cell, so brush weights land beside their masks
def test_up_places_cell_values_at_cell_centres():
    g = np.arange(12, dtype=np.float32).reshape(3, 4)
    u = S.up(g, 4, (12, 16))
    assert u.shape == (12, 16)
    # block b's centre is at b + 0.5, i.e. cell coordinate (b + 0.5) / 4 - 0.5; with rows +4 and columns +1 per cell
    # the upsample is the plane 4 * zc + xc wherever it is not clamped at the border
    zc = (np.arange(12) + 0.5) / 4 - 0.5
    xc = (np.arange(16) + 0.5) / 4 - 0.5
    plane = 4 * zc[:, None] + xc[None, :]
    assert np.allclose(u[2:10, 2:14], plane[2:10, 2:14], atol=1e-5)
    assert np.allclose(u[0, 0], g[0, 0]) and np.allclose(u[-1, -1], g[-1, -1]), "borders clamp to the edge cells"


# removing this lets y_to_raw drift from terrain.sample_to_height, so every sculpted column is written a raw step off
def test_y_to_raw_inverts_sample_to_height_within_one_raw_step():
    raw = np.arange(0, 65536, dtype=np.uint16)
    y = T.sample_to_height(raw, WORLD)
    back = S.y_to_raw(y, WORLD).astype(np.int64)
    top = int(round(IMPORT["high_in"] * 65535))
    live = raw.astype(np.int64) <= top
    assert np.abs(back[live] - raw[live]).max() <= 1
    assert (back[~live] == top).all(), "raw values above high_in clamp to y200 and come back as its raw value"
    # the float32 heights main() works on round-trip the same way
    back32 = S.y_to_raw(y.astype(np.float32), WORLD).astype(np.int64)
    assert np.abs(back32[live] - raw[live]).max() <= 1


def _apply_fixture(tmp_path, monkeypatch, change):
    """A tmp repository and source root for sculpt.main apply, with run() stubbed to return change(heights)."""
    repo, src, out = tmp_path / "repo", tmp_path / "src", tmp_path / "out"
    (repo / "data").mkdir(parents=True)
    src.mkdir()
    out.mkdir()
    rng = np.random.default_rng(3)
    raw = rng.integers(20000, 65536, size=(64, 96), dtype=np.int64).astype(np.uint16)
    raw[:, :8] = 65535                                    # clamped columns: y_to_raw(y200) is 65278, not 65535
    Image.fromarray(raw).save(src / "cut.png")
    sha = hashlib.sha256((src / "cut.png").read_bytes()).hexdigest()
    for name, doc in (("regions.json", {"subregions": []}), ("towns.json", {"towns": []}),
                      ("foliage.json", {}), ("landmarks.json", {"landmarks": []}),
                      ("rivers.json", {"cut": {"output": {"path": "cut.png", "sha256": sha}}})):
        (repo / "data" / name).write_text(json.dumps(doc), encoding="utf-8")
    wp = repo / "data" / "world.json"
    wp.write_text(json.dumps(WORLD), encoding="utf-8")
    cfgp = repo / "data" / "sculpt.json"
    cfgp.write_text(json.dumps({"schema": "cobblers.sculpt/1"}), encoding="utf-8")
    monkeypatch.setattr(S, "ROOT", repo)
    seen = {}

    def fake_run(heights, world, cfg, *rest, **kw):
        seen["heights"] = heights.copy()
        new = change(heights.copy())
        return new, [], np.zeros(heights.shape, np.uint8), {}
    monkeypatch.setattr(S, "run", fake_run)
    return raw, sha, repo, src, out, wp, cfgp, seen


# removing this lets apply rewrite every column from the float heights, so columns no brush touched change raw value
# (the clamped y200 columns here would all become 65278) and the import is no longer bit-identical outside brushes
def test_apply_copies_raw_values_back_where_nothing_changed(tmp_path, monkeypatch):
    def change(h):
        h[10:20, 30:40] += 2.0                            # a brush
        h[40:50, 0:8] -= 3.0                              # a brush over clamped columns
        h[30, :] += 5e-4                                  # float noise under the 1e-3 threshold
        return h
    raw, sha, repo, src, out, wp, cfgp, seen = _apply_fixture(tmp_path, monkeypatch, change)
    S.main(["apply", "--world", str(wp), "--source-root", str(src), "--config", str(cfgp), "--out-dir", str(out)])
    written = np.array(Image.open(out / "land_8k_16_sculpted.png"))
    assert written.dtype == np.uint16 and written.shape == raw.shape
    touched = np.zeros(raw.shape, bool)
    touched[10:20, 30:40] = True
    touched[40:50, 0:8] = True
    assert np.array_equal(written[~touched], raw[~touched])
    assert (raw[~touched] == 65535).any(), "the fixture has clamped untouched columns to catch a rewrite"
    want = S.y_to_raw(change(seen["heights"].copy()), WORLD)
    assert np.array_equal(written[touched], want[touched])
    report = json.loads((repo / "derived" / "sculpt" / "report.json").read_text(encoding="utf-8"))
    assert report["columns_touched"] == int(touched.sum())
    assert report["input"]["sha256"] == sha
    assert report["output"]["sha256"] == hashlib.sha256((out / "land_8k_16_sculpted.png").read_bytes()).hexdigest()
    assert (repo / "build" / "sculpt" / "coast_class.png").is_file()
    # the class map records the heightmap it belongs to, so paint_maps can refuse a stale one
    record = json.loads((repo / "build" / "sculpt" / "coast_class.json").read_text(encoding="utf-8"))
    assert record == {"heightmap_sha256": report["output"]["sha256"]}


# removing this lets apply sculpt a file that is not the river cut recorded in rivers.json
def test_apply_refuses_an_input_that_is_not_the_recorded_cut(tmp_path, monkeypatch):
    raw, sha, repo, src, out, wp, cfgp, seen = _apply_fixture(tmp_path, monkeypatch, lambda h: h)
    rivers = repo / "data" / "rivers.json"
    rivers.write_text(json.dumps({"cut": {"output": {"path": "cut.png", "sha256": "f" * 64}}}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        S.main(["apply", "--world", str(wp), "--source-root", str(src), "--config", str(cfgp), "--out-dir", str(out)])
    assert "is not the river cut" in str(e.value.code)
    assert not (out / "land_8k_16_sculpted.png").exists() and "heights" not in seen


# ------------------------------------------------------------------ coast profiles

BEACH = {"grade": [8, 15], "berm_blocks": [6, 18], "top_above_sea": [3.0, 5.5], "back_blocks": [40, 110],
         "shelf_grade": [12, 20], "shelf_depth": [3.5, 6]}
ESTUARY = {"grade": [28, 42], "berm_blocks": [16, 32], "top_above_sea": [2.0, 3.0], "back_blocks": [60, 120],
           "shelf_grade": [20, 28], "shelf_depth": [2, 3]}
SHORE = {"grade": [5, 7], "top_above_sea": [5.0, 7.5], "back_blocks": [45, 110], "shelf_grade": [8, 11],
         "shelf_depth": [3.5, 5]}
ROCKY = {"bank_grade": 1.8, "bank_top_above_sea": 7.0, "back_blocks": 50, "drop_grade": 1.4, "drop_depth": 9,
         "rugged": 1.0}
CLIFF = {"height": [10, 26], "relief_share": 0.35, "face_blocks": [1, 7], "back_blocks": [35, 110], "talus_blocks": 7,
         "drop_grade": 0.9, "drop_depth": 16}
D = np.arange(-400, 401, dtype=np.float32)        # signed distance, positive inland
NOISE = [(0.0, 0.0, 0.0, 0.0), (0.5, 0.5, 0.5, 0.5), (1.0, 1.0, 1.0, 1.0), (0.2, 0.9, 0.4, 0.7)]


def _ground(seed=0):
    """Irregular ground: 62 + d/6 with 8 blocks of noise, so equality checks cannot pass by coincidence."""
    rng = np.random.default_rng(seed)
    return (SEA + D / 6.0 + rng.uniform(-4, 4, D.shape)).astype(np.float32)


# removing this lets a beach or estuary shelf fill the seabed above its toe (sea + 0.35), turning open water into land
# beyond the berm
@pytest.mark.parametrize("spec", [BEACH, ESTUARY], ids=["beach", "estuary"])
@pytest.mark.parametrize("n", NOISE)
def test_beachlike_never_raises_seabed_above_the_toe(spec, n):
    for h0 in (np.full(D.shape, 40.0, np.float32), np.full(D.shape, SEA - 1.0, np.float32), _ground()):
        new = S.profile_beachlike(h0, D, SEA, spec, *n)
        E = spec["berm_blocks"][0] + (spec["berm_blocks"][1] - spec["berm_blocks"][0]) * n[1]
        sea_side = D < -E
        assert (new[sea_side] <= np.maximum(h0[sea_side], SEA + 0.35) + 1e-4).all()
        assert (new[sea_side] >= h0[sea_side] - 1e-4).all(), "the shelf only fills"


# removing this lets the strand's grade leave its configured range (a beach steeper than 1:8 or flatter than 1:15)
@pytest.mark.parametrize("name,fn,spec", [("beach", "profile_beachlike", BEACH), ("estuary", "profile_beachlike", ESTUARY),
                                          ("shore", "profile_shore", SHORE)])
@pytest.mark.parametrize("n1", [0.0, 0.5, 1.0])
def test_strand_grade_matches_the_configured_range(name, fn, spec, n1):
    h0 = np.full(D.shape, 150.0, np.float32)            # high ground, so the shore's cut-back strand shows
    new = getattr(S, fn)(h0, D, SEA, spec, n1, 0.5, 0.5, 0.5)
    lo, hi = spec["grade"]
    g = lo + (hi - lo) * n1
    top = spec["top_above_sea"][0] + (spec["top_above_sea"][1] - spec["top_above_sea"][0]) * 0.5
    if name == "shore":
        dtop = (top - 0.5) * g
    else:
        dtop = (top - 0.35) * g - (spec["berm_blocks"][0] + (spec["berm_blocks"][1] - spec["berm_blocks"][0]) * 0.5)
    strand = (D >= 1) & (D <= np.floor(dtop))           # from the shoreline to the strand's top
    assert strand.sum() >= 5
    rise = np.diff(new[strand])
    assert np.allclose(rise, 1.0 / g, atol=1e-4), (name, rise[:3], 1.0 / g)
    assert 1.0 / hi - 1e-6 <= rise.mean() <= 1.0 / lo + 1e-6


# removing this lets a profile keep changing ground past its back slope, so a coastal brush reaches far inland
@pytest.mark.parametrize("name", ["beach", "estuary", "shore", "rocky", "cliff"])
@pytest.mark.parametrize("n", NOISE)
def test_profiles_leave_ground_past_their_back_slope_unchanged(name, n):
    h0 = _ground(1)
    rug = np.random.default_rng(2).uniform(0, 1, D.shape).astype(np.float32)
    new = {"beach": lambda: S.profile_beachlike(h0, D, SEA, BEACH, *n),
           "estuary": lambda: S.profile_beachlike(h0, D, SEA, ESTUARY, *n),
           "shore": lambda: S.profile_shore(h0, D, SEA, SHORE, *n),
           "rocky": lambda: S.profile_rocky(h0, D, SEA, ROCKY, rug),
           "cliff": lambda: S.profile_cliff(h0, D, SEA, CLIFF, 60.0, n[1], rug, n[3])}[name]()
    far = D > 200
    assert np.array_equal(new[far], h0[far]), name
    assert not np.array_equal(new, h0), "the profile does change the shore itself"


# removing this lets a rocky or cliff coast fill the sea instead of deepening it (they only cut below the waterline,
# apart from the rocky rug band within 24 blocks of the shore)
@pytest.mark.parametrize("name", ["rocky", "cliff"])
def test_rocky_and_cliff_only_cut_the_seabed(name):
    h0 = _ground(4)
    rug = np.random.default_rng(5).uniform(0, 1, D.shape).astype(np.float32)
    if name == "rocky":
        new, sea_side = S.profile_rocky(h0, D, SEA, ROCKY, rug), D < -24
    else:
        new, sea_side = S.profile_cliff(h0, D, SEA, CLIFF, 60.0, 0.5, rug, 0.8), D < 0
    assert (new[sea_side] <= h0[sea_side] + 1e-4).all()


# ------------------------------------------------------------------ protection

PROTECT = {"settlement_margin_blocks": 8, "landmark_tree_margin_blocks": 4, "river_margin_blocks": 0,
           "lake_margin_blocks": 0, "feather_blocks": 24, "terrain_feather_blocks": 60}
TOWNS = {"towns": [
    {"id": "town", "footprint": {"min_x": 40, "min_z": 40, "max_x": 120, "max_z": 80}},
    {"id": "summit_pad", "footprint": {"min_x": 160, "min_z": 160, "max_x": 200, "max_z": 200}},
    {"id": "big_tree", "kind": "landmark_tree", "footprint": {"min_x": 160, "min_z": 40, "max_x": 200, "max_z": 80}},
]}


def _prot(shape="rect", lake=0, pads=("summit_pad",)):
    cfg = {"protect": dict(PROTECT, lake_margin_blocks=lake), "pads": [{"site": s} for s in pads]}
    return S.protection(256, TOWNS, {}, {"courses": []}, {"landmarks": []}, cfg, 4, shape)


def _at(p, x, z):
    return float(p[z // 4, x // 4])


# removing this lets a settlement's own ground or a landmark tree's glade lose protection (distance 0 means full
# weight: tools/sculpt.py run keeps the original column there)
def test_protection_is_zero_inside_sites_and_grows_outside():
    p = _prot()
    assert p.shape == (64, 64)
    assert _at(p, 80, 60) == 0 and _at(p, 44, 44) == 0 and _at(p, 180, 60) == 0
    assert _at(p, 80, 160) > 0 and _at(p, 80, 240) > _at(p, 80, 120)
    weight = 1 - np.clip(p / PROTECT["feather_blocks"], 0, 1)
    assert weight[60 // 4, 80 // 4] == 1.0


# removing this lets a pad site be protected, so the pad pressed there is undone by protection
def test_protection_skips_pad_sites():
    assert _at(_prot(), 180, 180) > 0
    assert _at(_prot(pads=()), 180, 180) == 0


# removing this lets mountain sites (circle) keep square mesas, or coast sites (rect) lose their corners
def test_protection_circle_is_inscribed_and_rect_keeps_corners():
    rect, circ = _prot("rect"), _prot("circle")
    corner = (36, 36)                              # inside the town footprint plus margin, outside its inscribed circle
    assert _at(rect, *corner) == 0 and _at(circ, *corner) > 0
    assert _at(circ, 80, 60) == 0, "the centre of the site stays protected"
    assert (circ == 0).sum() < (rect == 0).sum()


# Documented behaviour (the comment in protection()): lake_margin_blocks, at least one 4-block cell, grows every
# protected feature, settlements included, on top of their own margin; square footprints rely on that growth to cover
# corners just outside their inscribed circle. Removing this lets the growth vanish (corners lose protection) or
# exceed the configured amount (more terrain frozen than data/sculpt.json says).
@pytest.mark.parametrize("lake", [0, 16, 20])
def test_lake_margin_grows_every_protected_site_by_at_least_one_cell(lake):
    p = _prot(lake=lake)
    zs, xs = np.nonzero(p == 0)
    town = (zs * 4 >= 40) & (zs * 4 < 80) & (xs * 4 < 140)
    cells = max(1, lake // 4)
    first_margin_cell = (40 - PROTECT["settlement_margin_blocks"]) // 4
    assert xs[town].min() == first_margin_cell - cells, (lake, int(xs[town].min()))


# ------------------------------------------------------------------ volcano forms

VOLCANO = {"steep_faces_deg": 250, "shift_blocks": 0, "shift_taper_blocks": 100, "shift_from_y": 135}
DOME = {"id": "dome", "form": "lava_dome", "centre": [300, 300], "dome_radius": 40, "dome_top_y": 199, "dome_drop": 12,
        "spines": 3, "spine_radius": 4, "spine_seed": 7}
CINDER = {"id": "cinder", "form": "cinder_cone", "centre": [300, 300], "top_y": 189, "slope": 0.62, "radius": 75,
          "crater_radius": 14, "crater_floor_y": 180, "strength": 0.7, "plain_y": 100}
CALDERA = {"id": "caldera", "form": "caldera", "centre": [300, 300], "floor_radius": 50, "floor_y": 104,
           "wall_to_radius": 70, "rim_to_radius": 80, "rim_y": 150, "rim_noise": 4, "flank_to_radius": 150,
           "flank_grade": 0.2}
REACH = {"lava_dome": DOME["dome_radius"] + 45, "cinder_cone": CINDER["radius"] + 120}


# removing this lets a lava dome or cinder cone lower ground far beyond the cone (both cut everything above their
# surface, which keeps falling with distance, so without the reach limit a plateau hundreds of blocks away is cut)
@pytest.mark.parametrize("cone", [DOME, CINDER], ids=["lava_dome", "cinder_cone"])
def test_dome_and_cinder_cone_stay_inside_their_reach(cone):
    h = np.full((600, 600), 150.0, np.float32)             # a plateau above the cinder cone's plain
    out = S.sculpt_volcano(h, dict(VOLCANO, cones=[cone]), (0, 0, 600, 600), 600, 5)
    zz, xx = np.mgrid[0:600, 0:600]
    r = np.hypot(xx - 300, zz - 300)
    outside = r >= REACH[cone["form"]]
    assert outside.sum() > 10000
    assert np.array_equal(out[outside], h[outside])
    assert np.abs(out[r < cone.get("dome_radius", cone.get("radius"))] - 150).max() > 5, "the cone itself is shaped"


# removing this lets the caldera floor tilt, rise or move off its centre (calderas are not carried by the wind shift)
@pytest.mark.parametrize("shift", [0, 25])
def test_caldera_floor_is_flat_at_floor_y_inside_floor_radius(shift):
    h = np.full((600, 600), 150.0, np.float32)
    zz, xx = np.mgrid[0:600, 0:600]
    h = (h + 0.05 * (xx - 300)).astype(np.float32)          # tilted ground, so a floor that followed it would show
    out = S.sculpt_volcano(h, dict(VOLCANO, shift_blocks=shift, cones=[CALDERA]), (0, 0, 600, 600), 600, 5)
    r = np.hypot(xx - 300, zz - 300)
    inside = r <= CALDERA["floor_radius"]
    assert np.allclose(out[inside], CALDERA["floor_y"])
    assert (out[(r > CALDERA["wall_to_radius"]) & (r <= CALDERA["rim_to_radius"])] > CALDERA["floor_y"] + 30).all()


# ------------------------------------------------------------------ run() on a synthetic island

@pytest.fixture(scope="module")
def island():
    cfg_real = json.loads((ROOT / "data" / "sculpt.json").read_text(encoding="utf-8"))
    n = 1024
    zz, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    r = np.hypot(xx - 512, zz - 512)
    h = np.clip(62 + (360 - r) * 0.12, 20, 120).astype(np.float32)        # island radius 360, coast ramp 1:8
    cfg = {"prevailing_wind_from_deg": 250, "protect": dict(PROTECT, settlement_margin_blocks=32),
           "coast": dict(copy.deepcopy(cfg_real["coast"]), band_blocks=120,
                         classes={"beach": dict(BEACH, micro_relief=0.25), "estuary": dict(ESTUARY, micro_relief=0.15),
                                  "shore": dict(SHORE, berm_blocks=[0, 0], micro_relief=0.9),
                                  "rocky": dict(ROCKY, micro_relief=0.9), "cliff": dict(CLIFF, micro_relief=0.9)}),
           "massifs": [],
           # a stratovolcano in deep water: its forms only cut down to a surface far above the seabed, so it changes
           # nothing, but run() needs a cone to box the volcano stage
           "volcano": dict(VOLCANO, cones=[{"id": "far", "form": "stratovolcano", "centre": [60, 60],
                                            "crater_radius": 48, "crater_floor_y": 174, "rim_y": 200, "rim_width": 14,
                                            "flank_to_radius": 240, "flank_drop": 35, "breach_bearing_deg": 90,
                                            "breach_half_angle_deg": 28, "breach_floor_y": 176, "breach_grade": 0.15}]),
           "pads": []}
    regions = {"regions": [{"id": "isle"}], "subregions": [
        {"id": "isle_sub", "parent": "isle", "polygons": [[[100, 100], [924, 100], [924, 924], [100, 924]]]}]}
    towns = {"towns": [{"id": "port", "centre": {"x": 512, "z": 190},
                        "footprint": {"min_x": 462, "min_z": 150, "max_x": 562, "max_z": 230}},
                       # a large square harbour on the south coast: its corners lie outside the circle inscribed in
                       # the footprint plus margin (hypot(100, 100) = 141 > 100 + 32)
                       {"id": "harbour", "centre": {"x": 512, "z": 844},
                        "footprint": {"min_x": 412, "min_z": 744, "max_x": 612, "max_z": 944}},
                       # a square quay on the exposed west coast whose corners fall within the one-cell growth of
                       # its circle (80 + 32 < hypot(80, 80) = 113 <= 80 + 32 + 4)
                       {"id": "quay", "centre": {"x": 180, "z": 512},
                        "footprint": {"min_x": 100, "min_z": 432, "max_x": 260, "max_z": 592}}]}
    world = {"vertical": {"sea_level": 62}, "import": IMPORT, "heightmap": {"bit_depth": 16}}
    new, rows, class_map, report = S.run(h, world, cfg, regions, {"courses": [], "cut": {}}, towns, {},
                                         {"landmarks": []})
    return h, r, new, rows, class_map, report, cfg


# removing this lets the coastal brush change ground beyond band_blocks from the shoreline, inland or out to sea
def test_run_leaves_ground_beyond_the_coastal_band_unchanged(island):
    h, r, new, rows, class_map, report, cfg = island
    band = cfg["coast"]["band_blocks"]
    far = np.abs(r - 360) > band + 16                        # the shoreline is the r = 360 circle, give or take a cell
    assert np.array_equal(new[far], h[far])
    assert report["coast"]["columns_changed_half_block"] > 10000, "the band itself is sculpted"


# removing this lets the ground in the middle of a settlement inside the coastal band be reshaped (its columns must
# come back under the 1e-3 blocks apply uses to copy the raw value back)
def test_run_keeps_the_middle_of_protected_settlements(island):
    h, r, new, rows, class_map, report, cfg = island
    zz, xx = np.mgrid[0:h.shape[0], 0:h.shape[1]]
    for cx, cz in ((512, 190), (512, 844)):
        middle = np.hypot(xx - cx, zz - cz) <= 40
        assert (np.abs(r[middle] - 360) < cfg["coast"]["band_blocks"]).all(), "the site sits in the coastal band"
        assert np.abs(new[middle] - h[middle]).max() < 1e-3
    assert np.abs(new - h)[744:945, 300:412].max() > 1.0, "the coast beside the harbour is sculpted"


# Documented behaviour: a site is protected by the circle inscribed in its footprint plus margin, grown by
# lake_margin_blocks (at least one cell), with a box-smoothed weight, so footprint edges and corners may move by a
# fraction of a block. Removing this lets a brush move a column by half a block or more in a footprint whose corners
# lie within the circle (port) or within its growth (quay; unprotected, its corners would move up to 2.4 blocks).
# Corners beyond the growth are not covered by the design: the harbour's move 1.4 blocks here, so only its middle is
# held (test_run_keeps_the_middle_of_protected_settlements). The real footprints are held to the same half-block bound
# by test_real_sculpt_moves_no_settlement_footprint_column_by_half_a_block.
FOOTPRINTS = {"port": (150, 231, 462, 563), "quay": (432, 593, 100, 261), "harbour": (744, 945, 412, 613)}


def test_run_moves_no_column_of_a_footprint_within_its_grown_circle_by_half_a_block(island):
    h, r, new, rows, class_map, report, cfg = island
    for name in ("port", "quay"):
        z0, z1, x0, x1 = FOOTPRINTS[name]
        moved = float(np.abs(new[z0:z1, x0:x1] - h[z0:z1, x0:x1]).max())
        assert moved < 0.5, (name, moved)
        beside = float(np.abs(new - h)[max(0, z0 - 150):z1 + 150, max(0, x0 - 150):x1 + 150].max())
        assert beside > 1.0, (name, "the coast around the footprint is sculpted, so the bound has teeth")
    z0, z1, x0, x1 = FOOTPRINTS["quay"]
    for zc, xc in ((z0, x0), (z0, x1 - 1), (z1 - 1, x0), (z1 - 1, x1 - 1)):
        corner = (slice(zc - 4, zc + 5), slice(xc - 4, xc + 5))
        assert np.abs(new[corner] - h[corner]).max() < 0.5, ("quay corner", zc, xc)


# Removing this lets the real sculpt move a settlement footprint column by half a block or more (the coordinator
# measured 0.22 at most, mining_town). Runs only when COBBLERS_SOURCE_ROOT holds both heightmaps with the sha256 values
# world.json records; otherwise skipped.
def test_every_settlement_still_stands_on_the_ground_it_was_sited_on():
    """The ground towns.json records for each footprint must still be the ground the canonical heightmap gives.

    This replaces a check that compared the *pre-sculpt river cut* against the current map. That baseline was
    three passes out of date -- sculpt, then the b145 rescale, then the pads -- so it asserted something no town
    was ever sited on: it failed at 86.97 blocks on tableland_stop against the current map, and still at 21.89 on
    sunset_west against the sculpt's own output. It only ever went green by skipping when COBBLERS_SOURCE_ROOT was
    unset, so the settlement guard has been inert since before the rescale (found 2026-09-22).

    The invariant that actually protects a town is that its recorded ground has not drifted from the map any
    later pass left behind -- whatever those passes were. Measured today: all 27 towns agree exactly, drift 0.0.
    Two settlements do not stand on the heightmap at all (the Displaced City on its cavern floor, Relic Island on
    an islet) and are excluded by data, not by name.
    """
    import os
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    hm = world["heightmap"]
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT unset")
    path = Path(root) / hm["path"]
    if not path.is_file():
        pytest.skip("the canonical heightmap is not under COBBLERS_SOURCE_ROOT")
    if hashlib.sha256(path.read_bytes()).hexdigest() != hm["sha256"]:
        pytest.skip("the heightmap on disk is not the one world.json records")
    now = T.sample_to_height(np.array(Image.open(path)), world)

    off_map = set()
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    for sid, s in placements["settlements"].items():
        if isinstance(s, dict) and s.get("ground") in ("cavern_floor", "islet"):
            off_map.add(sid)

    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    checked, worst = 0, (-1.0, "")
    for t in towns:
        fp = t.get("footprint") or {}
        gy = fp.get("ground_y")
        if fp.get("min_x") is None or not gy or t["id"] in off_map:
            continue
        sl = (slice(int(fp["min_z"]), int(fp["max_z"]) + 1), slice(int(fp["min_x"]), int(fp["max_x"]) + 1))
        checked += 1
        drift = max(abs(float(now[sl].min()) - float(gy[0])), abs(float(now[sl].max()) - float(gy[1])))
        worst = max(worst, (drift, t["id"]))
    assert checked >= 20, "only %d footprints checked" % checked
    assert worst[0] < 0.5, worst


# removing this lets the coast class map carry codes outside 1-5 or mark columns away from the coast, which paint_maps
# would turn into beaches inland
def test_run_class_map_codes_lie_near_the_coast(island):
    h, r, new, rows, class_map, report, cfg = island
    assert class_map.dtype == np.uint8 and class_map.shape == h.shape
    assert set(np.unique(class_map).tolist()) <= {0, 1, 2, 3, 4, 5} and (class_map > 0).any()
    assert (np.abs(r[class_map > 0] - 360) <= 130).all()
    assert {row["class"] for row in rows} <= set(S.CLASSES)
    assert report["coast"]["classes"] == {c: sum(1 for row in rows if row["class"] == c) for c in S.CLASSES}


# ------------------------------------------------------------------ coast_measure.profile_metrics

def _profile(inland_fn, offshore_fn):
    i = np.arange(CM.OFFSHORE + CM.INLAND + 1) - CM.OFFSHORE
    return np.where(i >= 0, inland_fn(np.maximum(i, 0)), offshore_fn(np.maximum(-i, 0))).astype(np.float64)


# removing this lets run_to, grade_0_4 or the offshore depth distances be counted from the wrong end of the profile
def test_profile_metrics_on_a_uniform_ramp():
    prof = _profile(lambda k: SEA + k / 8.0, lambda k: SEA - k / 4.0)
    m = CM.profile_metrics(prof, SEA)
    assert (m["run_to_+2"], m["run_to_+4"], m["run_to_+8"], m["run_to_+16"]) == (16, 32, 64, 128)
    assert m["grade_0_4"] == 0.125
    assert (m["depth_at_-3"], m["depth_at_-8"], m["depth_at_-15"]) == (12, 32, 60)
    assert m["steps"] == 0 and m["flat_share"] == 0.0


# removing this lets a staircase coast (flat treads and one-block risers) read as a smooth slope
def test_profile_metrics_counts_steps_on_a_stepped_ramp():
    tread = 10
    prof = _profile(lambda k: SEA + np.floor(k / (tread + 1)), lambda k: SEA - k / 4.0)
    m = CM.profile_metrics(prof, SEA)
    assert m["run_to_+16"] == 16 * (tread + 1)
    assert m["steps"] >= 14 and m["flat_share"] > 0.7
    smooth = CM.profile_metrics(_profile(lambda k: SEA + k / (tread + 1), lambda k: SEA - k / 4.0), SEA)
    assert smooth["steps"] == 0


# removing this lets a coast that never reaches +N report a distance instead of None
def test_profile_metrics_reports_none_when_never_reached():
    m = CM.profile_metrics(_profile(lambda k: SEA + 0 * k + 1.0, lambda k: SEA + 0 * k), SEA)
    assert m["run_to_+2"] is None and m["grade_0_4"] is None and m["depth_at_-3"] is None


# removing this lets coast_measure.bilinear clamp x to the row count again (the bug fixed in sculpt.bilinear), so a
# profile over a non-square crop samples the wrong columns
def test_coast_measure_bilinear_on_a_non_square_array():
    zz, xx = np.mgrid[0:4, 0:10].astype(np.float32)
    h = 10 * zz + xx
    xs, zs = np.array([7.5]), np.array([1.0])
    assert np.allclose(CM.bilinear(h, xs, zs), 10 * zs + xs)
