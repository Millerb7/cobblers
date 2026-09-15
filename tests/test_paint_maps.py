"""tools/paint_maps.py: region plan -> WorldPainter paint maps (manifest contract of tools/worldpainter/paint.js).

Runs on a 256x256 grid (PP.N monkeypatched) with a synthetic island heightmap and fixture regions/landmarks,
plus data checks on the real data/regions.json and data/landmarks.json.

The main fixture runs foliage placement on purpose, with a fixture data/foliage.json, a fixture object library
(rows only; paint_maps never opens the .nbt files) and a fixture settlement: the "allowed" mask is only
consumed by tools/foliage.py, so the rules it carries (nothing on sea, shore, cliffs, lakes, creek beds or above
the treeline) are checked both on the mask main() hands to placement and on the objects_*.png it writes. The
real data/foliage.json does not map the fixture presets to any type, so running it here would place nothing
and prove nothing. One test runs main() with --foliage '' to pin the no-trees path.

Not covered: whether WorldPainter 2.27.1 accepts these maps (terrain names, plant names, biome ids, layer
behaviour on flooded columns, custom object offsets and rotation) and what the exported world looks like. That
needs a WorldPainter run and an in-game look, recorded as an experiment; nothing here touches the real
8192x8192 heightmap.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import paint_maps as PP  # noqa: E402

SMALL_N = 256
SEA = 62
OCEAN_IDS = {0, 10, 24, 44, 46, 48, 49, 50}
JITTER = 8.0  # paint_maps wobbles elevation bands by (noise - 0.5) * 16 blocks

# ------------------------------------------------------------------ fixture geometry (N = 256)

ISLAND_C, ISLAND_R = (128, 128), 100          # land at y80
SHORE_R = 106                                  # a flat y63 beach ring from r 100 to 106, then sea
HILL_C, HILL_TOP_R, HILL_R = (170, 128), 12, 50  # plateau y160, cone flanks down to y80
LAKE_C, LAKE_R, LAKE_FLOOR, LAKE_LEVEL = (80, 90), 12, 70, 75
LAKE_BASIN = [[64, 74], [96, 74], [96, 106], [64, 106]]
DRY_BASIN = [[100, 40], [120, 40], [120, 60], [100, 60]]  # all ground at y80, above its level
CREEK = [[60, 160], [110, 200]]
TREELINE = 120

PRESETS = {
    "frosty_woods": {
        "biome": "minecraft:snowy_taiga", "terrain": "SNOW",
        "plants": [{"set": "grassland", "coverage": 0.5}],
        "frost": True,
    },
    "banded_hill": {
        "biome_bands": [[100, "minecraft:meadow"], [None, "minecraft:stony_peaks"]],
        "terrain": "GRASS",
        "treeline_y": TREELINE,
    },
}

# ------------------------------------------------------------------ fixture foliage (tools/foliage.py inputs)

TOWN_FOOTPRINT = {"min_x": 40, "min_z": 112, "max_x": 56, "max_z": 128}
CLEARANCE = 6
LANDMARK_SITE = (100, 140)
LANDMARK_GLADE = 12
# the landmark tree's outpost in towns.json: its footprint is the glade square, as in data/towns.json
LANDMARK_FOOTPRINT = {"min_x": LANDMARK_SITE[0] - LANDMARK_GLADE, "max_x": LANDMARK_SITE[0] + LANDMARK_GLADE,
                      "min_z": LANDMARK_SITE[1] - LANDMARK_GLADE, "max_z": LANDMARK_SITE[1] + LANDMARK_GLADE}
# wider than the mask's own margins (shore ring 6, lake bank 3), so only the block-scale clearance keeps the ground
# next to the sea and the lake empty
WATER_CLEARANCE = 8
FOLIAGE = {
    "schema": "cobblers.foliage/1",
    "density_model": {"noise": {"ragged_scale": 96, "glade_scale": 320, "clump_scale": 72},
                      "water_clearance_blocks": WATER_CLEARANCE, "settlement_clearance_blocks": CLEARANCE},
    "types": {
        "fixture_forest": {
            "stems_per_ha": 500, "edge_width": 8, "ragged": 0, "glade_share": 0, "clumping": 0,
            "slope_lo": 30, "slope_hi": 45,
            "classes": [{"group": "ancient_spruce", "core": 1, "edge": 1, "spacing": 8},
                        {"group": "spruce", "core": 1, "edge": 1, "spacing": 4}],
            "debris": [{"group": "boulder", "per_ha": 80, "zone": "any", "max_slope": 45, "vertical_offset": -1},
                       {"group": "fallen_log_conifer", "per_ha": 80, "zone": "any", "max_slope": 45}],
            "understory": {"core": {"set": "fern_floor", "coverage": 0.5, "clear": False},
                           "mid": {"set": "fern_floor", "coverage": 0.5, "clear": False},
                           "edge": {"set": "fern_floor", "coverage": 0.5, "clear": False}},
        },
    },
    "preset_defaults": {"frosty_woods": "fixture_forest", "banded_hill": "fixture_forest"},
    "assign": {},
    "landmark_trees": [
        {"id": "fixture_giant", "object": "landmark_fixture", "site": list(LANDMARK_SITE),
         "glade_radius": LANDMARK_GLADE, "seen_from": []},
        {"id": "far_giant", "object": "landmark_fixture", "site": [5000, 5000], "glade_radius": 12, "seen_from": []},
    ],
}


def _row(name, group, origin, fp=1, height=8, crown=3.0, ground=0):
    return {"name": name, "file": name + ".nbt", "group": group, "source": "generated", "origin": origin,
            "sha256": "0" * 64, "size": [9, height, 9], "blocks": 10, "height": height, "crown_radius": crown,
            "trunk_footprint": fp, "depth_below_origin": 0, "eye_width": 1, "ground_radius": ground}


# distinct x, y, z in every origin so an axis swap in the manifest offset shows
LIBRARY = {"schema": "cobblers.foliage_library/1", "objects": [
    _row("ancient_spruce_01", "ancient_spruce", [5, 1, 7], fp=4, height=30, crown=6.0, ground=1),
    _row("ancient_spruce_02", "ancient_spruce", [6, 2, 4], fp=4, height=34, crown=6.5, ground=2),
    _row("spruce_01", "spruce", [3, 0, 2]),
    _row("boulder_01", "boulder", [2, 0, 1], height=2, crown=1.0, ground=2),
    _row("fallen_spruce_01", "fallen_log_conifer", [1, 0, 4], fp=6, height=3, crown=0.0, ground=5),
    _row("landmark_fixture", "landmark_fixture", [12, 2, 13], fp=16, height=40, crown=10.0, ground=6),
]}
# ground contact radius placement must keep clear, per group: the largest over the group's variants
GROUND = {}
for _r in LIBRARY["objects"]:
    GROUND[_r["group"]] = max(GROUND.get(_r["group"], 0), _r["ground_radius"])


def _square(x0, z0, x1, z1):
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def _sub(sid, preset, ring, area):
    return {"id": sid, "parent": "test_isle", "measured": {"area_km2": area}, "paint": {"preset": preset},
            "polygons": [ring], "encounters": {"table": None}}


def _regions(presets=PRESETS, hill_preset="banded_hill"):
    # The small hill sub-region is listed first so list order alone would let the big one paint over it.
    return {
        "paint_presets": presets,
        "regions": [{"id": "test_isle"}],
        "subregions": [
            _sub("hill", hill_preset, _square(115, 73, 225, 183), 0.012),
            _sub("woods", "frosty_woods", _square(10, 10, 246, 246), 0.056),  # reaches past the coast into sea
        ],
    }


LANDMARKS = {"landmarks": [
    {"id": "fixture_lake", "kind": "lake", "water_body": {"level_y": LAKE_LEVEL, "basin_polygons": [LAKE_BASIN]}},
    {"id": "dry_pond", "kind": "lake", "water_body": {"level_y": 70, "basin_polygons": [DRY_BASIN]}},
    {"id": "fixture_creek", "kind": "ravine", "axes": [{"id": "channel", "polyline": CREEK}]},
]}


def _heights():
    zz, xx = np.mgrid[0:SMALL_N, 0:SMALL_N].astype(np.float32)
    r_island = np.hypot(xx - ISLAND_C[0], zz - ISLAND_C[1])
    h = np.where(r_island <= ISLAND_R, 80.0, np.where(r_island <= SHORE_R, 63.0,
                 np.where(r_island <= ISLAND_R + 15, 50.0, 20.0))).astype(np.float32)
    r_hill = np.hypot(xx - HILL_C[0], zz - HILL_C[1])
    cone = 160.0 - (r_hill - HILL_TOP_R) * (80.0 / (HILL_R - HILL_TOP_R))
    h = np.where(r_hill <= HILL_TOP_R, 160.0, np.where(r_hill <= HILL_R, np.maximum(cone, 80.0), h))
    r_lake = np.hypot(xx - LAKE_C[0], zz - LAKE_C[1])
    h = np.where(r_lake <= LAKE_R, float(LAKE_FLOOR), np.where(r_lake <= LAKE_R + 3, LAKE_LEVEL + 1.0, h))  # low bank
    return h.astype(np.float32)


WORLD = {"heightmap": {"sha256": "x"}, "vertical": {"sea_level": SEA}, "import": {"water_level": SEA}}


def _write_inputs(d, regions=None, landmarks=None):
    rp, lp = d / "regions.json", d / "landmarks.json"
    rp.write_text(json.dumps(regions if regions is not None else _regions()), encoding="utf-8")
    lp.write_text(json.dumps(landmarks if landmarks is not None else LANDMARKS), encoding="utf-8")
    fp, tp = d / "foliage.json", d / "towns.json"
    fp.write_text(json.dumps(FOLIAGE), encoding="utf-8")
    tp.write_text(json.dumps({"towns": [{"id": "hamlet", "footprint": TOWN_FOOTPRINT},
                                        {"id": "fixture_giant", "kind": "landmark_tree",
                                         "footprint": LANDMARK_FOOTPRINT}]}), encoding="utf-8")
    lib = d / "lib" / "library.json"
    lib.parent.mkdir(exist_ok=True)
    lib.write_text(json.dumps(LIBRARY), encoding="utf-8")
    return rp, lp, fp, tp, lib


def _run_main(mp, d, regions=None, landmarks=None, foliage=True, seen=None):
    """seen: optional dict that receives the allowed and water masks main() hands to placement."""
    mp.setattr(PP, "N", SMALL_N)
    heights = _heights()
    mp.setattr(PP.T, "load_from_args", lambda args: (heights.copy(), json.loads(json.dumps(WORLD))))
    rp, lp, fp, tp, lib = _write_inputs(d, regions, landmarks)
    if seen is not None:
        real = PP.paint_foliage

        def spy(*args):
            seen["allowed"], seen["water"] = args[12].copy(), args[14].copy()
            return real(*args)
        mp.setattr(PP, "paint_foliage", spy)
    out = d / "paint"
    rc = PP.main(["--regions", str(rp), "--landmarks", str(lp), "--out", str(out), "--seed", "7", "--rivers", "",
                  "--foliage", str(fp) if foliage else "", "--library", str(lib), "--towns", str(tp)])
    return rc, out, heights


def _png(path):
    img = Image.open(path)
    return img, np.asarray(img)


def _mask(ring):
    from PIL import ImageDraw
    img = Image.new("L", (SMALL_N, SMALL_N), 0)
    ImageDraw.Draw(img).polygon([tuple(p) for p in ring], fill=1)
    return np.asarray(img).astype(bool)


def _line_mask(polyline, width=10):
    from PIL import ImageDraw
    img = Image.new("L", (SMALL_N, SMALL_N), 0)
    ImageDraw.Draw(img).line([tuple(p) for p in polyline], fill=1, width=width)
    return np.asarray(img).astype(bool)


@pytest.fixture(scope="module")
def painted(tmp_path_factory):
    d = tmp_path_factory.mktemp("paint")
    seen = {}
    with pytest.MonkeyPatch.context() as mp:
        rc, out, heights = _run_main(mp, d, seen=seen)
        # the real slope function, so the >40 degree rule is checked against what main() actually used
        slope = PP.T.slope_degrees(heights)
    maps = {p.name: np.asarray(Image.open(p)) for p in out.glob("*.png")}
    return {"rc": rc, "out": out, "h": heights, "slope": slope, "maps": maps, "allowed": seen["allowed"],
            "water": seen["water"], "lib_dir": d / "lib",
            "manifest": json.loads((out / "manifest.json").read_text(encoding="utf-8")),
            "stats": json.loads((out / "stats.json").read_text(encoding="utf-8"))}


def _positions(painted):
    """group -> (xs, zs) of every column an objects_*.png marks."""
    out = {}
    for e in painted["manifest"]["objects"]:
        zs, xs = np.nonzero(painted["maps"][e["map"]])
        out[e["layer"]] = (xs, zs)
    return out


def _sub_masks():
    """Pixel masks per fixture sub-region as main() resolves them (hill wins inside its square)."""
    hill = _mask(_square(115, 73, 225, 183))
    woods = _mask(_square(10, 10, 246, 246)) & ~hill
    return hill, woods


# ------------------------------------------------------------------ 1. value_noise

# Removing this lets noise leave [0, 1] or change shape, which would push tree densities and coverages out of range.
def test_value_noise_is_unit_range_full_grid_and_seeded(monkeypatch):
    monkeypatch.setattr(PP, "N", SMALL_N)
    a = PP.value_noise(64, 123)
    assert a.shape == (SMALL_N, SMALL_N)
    assert np.isfinite(a).all() and a.min() >= 0.0 and a.max() <= 1.0
    assert np.array_equal(a, PP.value_noise(64, 123)), "same seed must repaint identically"
    assert not np.array_equal(a, PP.value_noise(64, 124)), "different seeds must differ"


# Removing this lets the noise grids silently double in memory (8192^2 float64 = 512 MB each, several cached).
def test_value_noise_is_float32(monkeypatch):
    monkeypatch.setattr(PP, "N", SMALL_N)
    assert PP.value_noise(64, 1).dtype == np.float32


# ------------------------------------------------------------------ 2. rasterise_subregions / fill_gaps

# Removing this lets a small sub-region inside a large one vanish under the large one's paint.
def test_rasterise_draws_larger_subregions_first(monkeypatch):
    monkeypatch.setattr(PP, "N", SMALL_N)
    subs = [_sub("small", "p", _square(100, 100, 140, 140), 0.001),
            _sub("big", "p", _square(20, 20, 220, 220), 0.04),
            _sub("medium", "p", _square(30, 30, 90, 90), 0.004)]
    idx = PP.rasterise_subregions(subs)
    assert idx.dtype == np.uint8 and idx.shape == (SMALL_N, SMALL_N)
    assert idx[120, 120] == 1, "small sub-region inside big keeps its own 1-based index"
    assert idx[60, 60] == 3
    assert idx[200, 200] == 2
    assert idx[5, 5] == 0 and idx[250, 250] == 0, "outside every polygon stays 0"
    assert set(np.unique(idx)) == {0, 1, 2, 3}


# Removing this lets degenerate rings (<3 points) crash the rasteriser.
def test_rasterise_skips_degenerate_rings(monkeypatch):
    monkeypatch.setattr(PP, "N", SMALL_N)
    s = _sub("a", "p", _square(10, 10, 50, 50), 0.001)
    s["polygons"].append([[0, 0], [5, 5]])
    idx = PP.rasterise_subregions([s])
    assert idx[30, 30] == 1 and idx[2, 2] == 0


# Removing this lets unpainted land slivers (or painted sea) appear along sub-region seams.
def test_fill_gaps_fills_land_only(monkeypatch):
    monkeypatch.setattr(PP, "N", SMALL_N)
    idx = np.zeros((SMALL_N, SMALL_N), np.uint8)
    idx[:, :100] = 3
    idx[:, 110:] = 5
    land = np.zeros((SMALL_N, SMALL_N), bool)
    land[:, :200] = True
    out = PP.fill_gaps(idx.copy(), land)
    gap = land & (idx == 0)
    assert gap.any()
    assert (out[gap] > 0).all(), "every land gap is assigned from a neighbour"
    assert set(np.unique(out[gap])) <= {3, 5}
    assert (out[~land] == idx[~land]).all(), "sea pixels are never assigned"
    assert (out[:, 230:] == idx[:, 230:]).all()
    # a sea gap between regions stays 0
    idx2 = idx.copy()
    land2 = land.copy()
    land2[:, 100:110] = False
    out2 = PP.fill_gaps(idx2, land2)
    assert (out2[:, 100:110] == 0).all()


# ------------------------------------------------------------------ 3. outputs and manifest contract

# Removing this lets main() skip a map paint.js reads, which fails only inside WorldPainter.
def test_main_writes_every_output(painted):
    out = painted["out"]
    assert painted["rc"] == 0
    for name in ("biomes.png", "terrain.png", "frost.png", "manifest.json", "stats.json", "canopy.npz",
                 "objects_ancient_spruce.png", "objects_spruce.png", "objects_boulder.png",
                 "objects_fallen_log_conifer.png", "objects_landmark_fixture.png", "plants_grassland.png",
                 "water_fixture_lake.png"):
        assert (out / name).is_file(), name
    assert not list(out.glob("trees_*.png")), "tree layers are retired; trees are objects"


# Removing this lets a map be written as RGB/16-bit or misaligned, which paint.js reads as wrong levels.
def test_full_maps_are_8bit_grayscale_full_grid(painted):
    for p in painted["out"].glob("*.png"):
        img, arr = _png(p)
        assert img.mode == "L", p.name
        assert arr.dtype == np.uint8, p.name
        if not p.name.startswith("water_"):
            assert arr.shape == (SMALL_N, SMALL_N), p.name


# Removing this lets values outside what paint.js maps (15 = one object, 0/1 masks) reach WorldPainter.
def test_map_value_ranges_match_paint_js(painted):
    m = painted["maps"]
    js = (ROOT / "tools" / "worldpainter" / "paint.js").read_text(encoding="utf-8")
    assert "fromLevel(15).toLevel(15)" in js, "paint.js applies object maps at level 15 only"
    for e in painted["manifest"]["objects"]:
        assert set(np.unique(m[e["map"]])) == {0, 15}, e["map"]
    for k in PP.PLANT_SETS:
        assert set(np.unique(m["plants_%s.png" % k])) <= {0, 1}
    assert set(np.unique(m["frost.png"])) <= {0, 1}
    codes = {int(c) for c in painted["manifest"]["terrain_codes"]}
    assert set(np.unique(m["terrain.png"])) <= codes | {0}
    wp_ids = set(PP.WP_BIOMES.values())
    assert set(np.unique(m["biomes.png"])) <= wp_ids | {255}


# Removing this lets the manifest list empty layers (wasted passes) or omit used ones (missing cover).
def test_manifest_lists_only_nonempty_layers(painted):
    man, m = painted["manifest"], painted["maps"]
    assert "trees" not in man, "the retired tree-layer key must not come back beside objects"
    layers = [e["layer"] for e in man["objects"]]
    assert layers == sorted(layers) and len(layers) == len(set(layers))
    assert set(layers) == {"ancient_spruce", "spruce", "boulder", "fallen_log_conifer", "landmark_fixture"}
    written = {p.name for p in painted["out"].glob("objects_*.png")}
    assert written == {"objects_%s.png" % g for g in layers}, "every map written is listed, and only those"
    for e in man["objects"]:
        assert e["map"] == "objects_%s.png" % e["layer"]
        assert e["count"] == int((m[e["map"]] == 15).sum()) > 0, e["layer"]
    names = [p["name"] for p in man["plants"]]
    assert names == ["cobblers_grassland", "cobblers_fern_floor"]
    assert man["plants"][0]["map"] == "plants_grassland.png"
    assert man["plants"][0]["plants"] == PP.PLANT_SETS["grassland"]
    assert man["biomes"] == "biomes.png" and man["terrain"] == "terrain.png" and man["frost"] == "frost.png"
    assert {int(k): v for k, v in man["terrain_codes"].items()} == {v: k for k, v in PP.TERRAIN_CODES.items()}
    assert man["source"]["heightmap_sha256"] == "x" and man["source"]["seed"] == 7


# Removing this lets an object's offset be un-negated or axis-swapped, so every tree lands beside or under its marked
# column (WorldPainter's Point3i is x, y horizontal and z up: the manifest offset is [-origin_x, -origin_z, -origin_y]).
def test_objects_manifest_offsets_negate_origin_in_xzy_order(painted):
    js = (ROOT / "tools" / "worldpainter" / "paint.js").read_text(encoding="utf-8")
    assert "new Point3i(o.offset[0], o.offset[1], o.offset[2])" in js
    rows = {}
    for r in LIBRARY["objects"]:
        rows.setdefault(r["group"], []).append(r)
    for e in painted["manifest"]["objects"]:
        want = rows[e["layer"]]
        assert len(e["objects"]) == len(want), "every variant of the group is offered, no other group's"
        for o, r in zip(e["objects"], want):
            ox, oy, oz = r["origin"]
            assert o["offset"] == [-ox, -oz, -oy], (e["layer"], r["name"])
            assert Path(o["file"]).is_absolute() and Path(o["file"]) == (painted["lib_dir"] / r["file"]).resolve()
            assert o["frequency"] == 1
            assert o["extend_foundation"] is PP.OBJECT_SETTINGS.get(e["layer"], {}).get("extend_foundation", True)
        want_vo = -1 if e["layer"] == "boulder" else 0
        assert all(o["vertical_offset"] == want_vo for o in e["objects"]), e["layer"]
    by = {e["layer"]: e for e in painted["manifest"]["objects"]}
    assert by["fallen_log_conifer"]["objects"][0]["extend_foundation"] is False, "a log lies on the ground"
    assert by["ancient_spruce"]["objects"][0]["extend_foundation"] is True, "a trunk reaches down to uneven ground"


# Removing this lets a lake be raised at the wrong place or level, or a dry basin be listed.
def test_manifest_water_entries_match_basin_crop(painted):
    water = painted["manifest"]["water"]
    assert [w["name"] for w in water] == ["fixture_lake"], "basins with no column below level are skipped"
    w = water[0]
    for key in ("level", "x", "z"):
        assert isinstance(w[key], int) and not isinstance(w[key], bool), key
    xs = [p[0] for p in LAKE_BASIN]
    zs = [p[1] for p in LAKE_BASIN]
    assert w["level"] == LAKE_LEVEL
    assert (w["x"], w["z"]) == (min(xs), min(zs))
    img, crop = _png(painted["out"] / w["mask"])
    # PIL fills polygon edges inclusively, so the bbox spans max - min + 1 blocks
    assert img.size == (max(xs) - min(xs) + 1, max(zs) - min(zs) + 1)
    full = _mask(LAKE_BASIN)
    assert np.array_equal(crop.astype(bool), full[w["z"]:w["z"] + img.size[1], w["x"]:w["x"] + img.size[0]])
    assert painted["stats"]["lakes"] == ["fixture_lake"]


# ------------------------------------------------------------------ 4. semantics

# Removing this lets a sub-region paint a biome other than its preset's.
def test_biome_follows_preset_and_height_bands(painted):
    b, h = painted["maps"]["biomes.png"], painted["h"]
    land = h >= SEA
    hill, woods = _sub_masks()
    assert (b[woods & land] == PP.WP_BIOMES["minecraft:snowy_taiga"]).all()
    low = hill & land & (h < 100 - JITTER)
    high = hill & land & (h >= 100 + JITTER)
    assert low.any() and high.any()
    assert (b[low] == PP.WP_BIOMES["minecraft:meadow"]).all()
    assert (b[high] == PP.WP_BIOMES["minecraft:stony_peaks"]).all()


# Removing this lets land biomes leak onto sea columns painted by coastal polygons.
def test_sea_gets_ocean_biome(painted):
    b, h = painted["maps"]["biomes.png"], painted["h"]
    sea = h < SEA
    assert sea.any()
    assert set(np.unique(b[sea])) <= OCEAN_IDS


# Removing this lets trunks stand on cliffs, above the treeline, in lake basins, on creek beds, the shore or the sea.
def test_allowed_mask_cleared_where_nothing_may_grow(painted):
    allowed, h, slope = painted["allowed"], painted["h"], painted["slope"]
    assert allowed.dtype == bool and allowed.shape == (SMALL_N, SMALL_N)
    hill, woods = _sub_masks()
    basin = _mask(LAKE_BASIN) & (h < LAKE_LEVEL + 2)
    assert (basin & (h >= LAKE_LEVEL)).any(), "fixture has a dry bank below level + 2"
    creek = _line_mask(CREEK) & (h >= SEA)
    shore = (h >= SEA) & (h < SEA + 3) & (slope < 20)
    above = hill & (h > TREELINE + JITTER) & (slope <= 40)      # the flat plateau, not the cliff
    for name, sel in (("cliff", slope > 40), ("treeline", above), ("lake basin", basin), ("creek", creek),
                      ("shore", shore), ("sea", h < SEA)):
        assert sel.any(), "fixture exercises %s" % name
        assert not allowed[sel].any(), name
    # the treeline is the preset's: the woods preset has none, so flat woods ground at any height is not cleared
    # positive control: flat woods land away from those rules is allowed, and so is a basin that holds no water
    from PIL import ImageFilter
    near_creek = np.asarray(Image.fromarray(_line_mask(CREEK).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    ok = woods & (h == 80) & (slope < 1) & ~_mask(LAKE_BASIN) & ~near_creek
    assert ok.any() and allowed[ok].all()
    dry = _mask(DRY_BASIN) & (slope < 1)
    assert dry.any() and allowed[dry].all(), "only columns below a basin's level + 2 are cleared"
    assert painted["stats"]["tree_allowed_pct"] == round(100.0 * allowed.mean(), 2)


def _dilate(mask, r):
    """True within Chebyshev distance r of a True column (the square an object's rotations can reach)."""
    n0, n1 = mask.shape
    pad = np.pad(mask, r, constant_values=False)
    out = np.zeros_like(mask)
    for dz in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= pad[r + dz:r + dz + n0, r + dx:r + dx + n1]
    return out


def _squares_all(mask, xs, zs, r):
    """For each position: the (2r+1) square around it lies on the map and mask is True over all of it."""
    n = mask.shape[0]
    return np.array([0 <= x - r and x + r < n and 0 <= z - r and z + r < n
                     and bool(mask[z - r:z + r + 1, x - r:x + r + 1].all())
                     for x, z in zip(xs.tolist(), zs.tolist())], bool)


# Removing this lets placement ignore the allowed mask over an object's ground contact, so under some rotation a
# trunk, root plate or fallen log rests on ground the mask forbids.
def test_objects_stand_only_on_allowed_columns(painted):
    allowed = painted["allowed"]
    pos = _positions(painted)
    assert sum(len(xs) for xs, _ in pos.values()) > 100, "fixture places enough objects to exercise the rule"
    for g, (xs, zs) in pos.items():
        if g == "landmark_fixture":
            continue
        assert len(xs) > 0, g
        assert _squares_all(allowed, xs, zs, GROUND[g]).all(), (g, GROUND[g])


# Removing this lets objects be painted on the seabed or in raised lake water wherever a polygon overhangs them.
def test_objects_never_on_sea_or_water(painted):
    h = painted["h"]
    wet = (h < SEA) | (_mask(LAKE_BASIN) & (h < LAKE_LEVEL))
    for e in painted["manifest"]["objects"]:
        assert not painted["maps"][e["map"]][wet].any(), e["layer"]


# Removing this lets an object's ground contact come within water_clearance_blocks of water. The clearance is applied
# at block resolution in paint_maps.paint_foliage; foliage.place on its own only clears whole 4-block water cells.
def test_objects_keep_water_clearance_blocks_from_water(painted):
    water = painted["water"]
    near = _dilate(water, WATER_CLEARANCE)
    placed = 0
    for g, (xs, zs) in _positions(painted).items():
        if g == "landmark_fixture":
            continue
        assert _squares_all(~near, xs, zs, GROUND[g]).all(), g
        placed += len(xs)
    # teeth: allowed ground inside the clearance band exists, so the mask alone would not keep it empty
    assert (painted["allowed"] & near).sum() > 500 and placed > 100


# Removing this lets trees, logs and boulders be placed with any ground contact inside a settlement or its margin.
def test_objects_keep_clear_of_settlements(painted):
    fp = TOWN_FOOTPRINT
    x0, x1 = fp["min_x"] - CLEARANCE, fp["max_x"] + CLEARANCE
    z0, z1 = fp["min_z"] - CLEARANCE, fp["max_z"] + CLEARANCE
    assert painted["allowed"][z0:z1 + 1, x0:x1 + 1].all(), "the clearance, not the mask, keeps this ground empty"
    for g, (xs, zs) in _positions(painted).items():
        if g == "landmark_fixture":
            continue
        r = GROUND[g]
        hit = (xs + r >= x0) & (xs - r <= x1) & (zs + r >= z0) & (zs - r <= z1)
        assert not hit.any(), (g, r)


# Removing this lets a landmark tree lose its glade, or a landmark sited off the map crash or vanish without a trace.
def test_landmark_tree_placed_alone_and_off_map_one_reported(painted):
    xs, zs = _positions(painted)["landmark_fixture"]
    assert list(zip(xs.tolist(), zs.tolist())) == [LANDMARK_SITE]
    for g, (gx, gz) in _positions(painted).items():
        if g == "landmark_fixture":
            continue
        d2 = (gx - LANDMARK_SITE[0]) ** 2 + (gz - LANDMARK_SITE[1]) ** 2
        assert (d2 >= LANDMARK_GLADE ** 2).all(), g
    assert painted["stats"]["foliage"]["types"]["_landmark_trees_outside_map"] == ["far_giant"]


# Removing this lets a landmark tree's outpost footprint (its glade square) plus the settlement margin clear a far
# wider square than glade_radius.
def test_landmark_tree_outposts_are_not_settlement_clearance(tmp_path, monkeypatch):
    monkeypatch.setattr(PP, "N", SMALL_N)
    tp = tmp_path / "towns.json"
    tp.write_text(json.dumps({"towns": [{"id": "hamlet", "footprint": TOWN_FOOTPRINT},
                                        {"id": "giant", "kind": "landmark_tree", "footprint": LANDMARK_FOOTPRINT},
                                        {"id": "unplaced", "footprint": {"min_x": None}}]}), encoding="utf-8")
    m = PP.settlement_clearance(str(tp), CLEARANCE)
    fp = TOWN_FOOTPRINT
    want = np.zeros((SMALL_N, SMALL_N), bool)
    want[fp["min_z"] - CLEARANCE:fp["max_z"] + CLEARANCE + 1, fp["min_x"] - CLEARANCE:fp["max_x"] + CLEARANCE + 1] = True
    assert np.array_equal(m, want)


# Removing this lets the landmark outpost exclusion come back in the painted output: nothing would stand between the
# glade and the outpost footprint plus margin.
def test_stems_grow_between_glade_and_landmark_outpost_margin(painted):
    lf = LANDMARK_FOOTPRINT
    x0, x1 = lf["min_x"] - CLEARANCE, lf["max_x"] + CLEARANCE
    z0, z1 = lf["min_z"] - CLEARANCE, lf["max_z"] + CLEARANCE
    found = 0
    for g, (xs, zs) in _positions(painted).items():
        if g == "landmark_fixture":
            continue
        found += int(((xs >= x0) & (xs <= x1) & (zs >= z0) & (zs <= z1)).sum())
    assert found > 0


# Removing this lets forest understory be painted onto sea or lake water inside a forest's sub-region, which the
# water passes had just cleared.
def test_understory_plants_never_on_water(painted):
    h = painted["h"]
    wet = (h < SEA) | (_mask(LAKE_BASIN) & (h < LAKE_LEVEL))
    assert painted["maps"]["plants_fern_floor.png"].any(), "the fixture paints understory at all"
    for k in PP.PLANT_SETS:
        name = "plants_%s.png" % k
        assert not painted["maps"][name][wet].any(), k


# Removing this lets --foliage '' still write object layers or a canopy, so a no-trees repaint keeps old trees.
def test_empty_foliage_places_no_objects(tmp_path, monkeypatch):
    rc, out, _ = _run_main(monkeypatch, tmp_path, foliage=False)
    assert rc == 0
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    assert man["objects"] == [] and "trees" not in man
    assert not list(out.glob("objects_*.png")) and not (out / "canopy.npz").exists()
    assert stats["foliage"] == {} and 0 < stats["tree_allowed_pct"] < 100


# Removing this lets snow cover vanish from frost presets or sit on raised lake water.
def test_frost_follows_preset_and_skips_wet_lake(painted):
    f, h = painted["maps"]["frost.png"], painted["h"]
    hill, woods = _sub_masks()
    wet = _mask(LAKE_BASIN) & (h < LAKE_LEVEL)
    assert wet.any()
    assert (f[woods & (h >= SEA) & ~wet] == 1).all()
    assert (f[wet] == 0).all()
    assert (f[hill & (h >= SEA)] == 0).all(), "banded_hill preset has no frost"


# Removing this lets lake beds keep grass/snow and creek beds keep the preset ground.
def test_lake_bed_and_creek_terrain(painted):
    t, h = painted["maps"]["terrain.png"], painted["h"]
    wet = _mask(LAKE_BASIN) & (h < LAKE_LEVEL)
    assert set(np.unique(t[wet])) <= {PP.TERRAIN_CODES["GRAVEL"], PP.TERRAIN_CODES["CLAY"]}
    creek = _line_mask(CREEK) & (h >= SEA)
    assert (t[creek] == PP.TERRAIN_CODES["GRAVEL"]).all()


# ------------------------------------------------------------------ 5. unknown preset

# Removing this lets a typo in a sub-region's preset crash later with a bare KeyError, or paint nothing.
def test_unknown_preset_exits_naming_subregion(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, tmp_path, regions=_regions(hill_preset="no_such_preset"))
    assert "hill" in str(e.value.code) and "no_such_preset" in str(e.value.code)


# ------------------------------------------------------------------ 6. plant names

# Names listed from org.pepsoft.worldpainter.layers.plants.Plants.ALL_PLANTS on WorldPainter 2.27.1 (the part of
# the list the plant sets may draw on); extend deliberately, from that list only.
KNOWN_PLANTS = {
    "Tall Grass", "Fern", "Large Fern", "Dead Shrub", "Dandelion", "Poppy", "Blue Orchid", "Allium",
    "Azure Bluet", "Red Tulip", "Orange Tulip", "White Tulip", "Pink Tulip", "Oxeye Daisy", "Sunflower", "Lilac",
    "Rose Bush", "Peony", "Red Mushroom", "Brown Mushroom", "Lily Pad", "Cornflower", "Lily of the Valley",
    "Sweet Berry Bush", "Bamboo", "Azalea", "Flowering Azalea", "Glow Lichen", "Moss Carpet", "Big Dripleaf",
    "Cherry Sapling", "Pink Petals",
}
# in WorldPainter's list, but on this server they exist only because VanillaBackport registers them under minecraft:
BACKPORT_ONLY = {"Leaf Litter", "Bush", "Firefly Bush", "Cactus Flower", "Short Dry Grass", "Tall Dry Grass",
                 "Wildflowers"}


# Removing this lets "Short Grass" back in (WorldPainter 2.27.1 writes minecraft:grass, invalid in 1.21.1), or a
# plant name WorldPainter does not know, or one that exists only through a backport mod.
def test_plant_sets_use_known_names_and_no_short_grass():
    for set_name, plants in PP.PLANT_SETS.items():
        assert "Short Grass" not in plants, set_name
        assert not set(plants) & BACKPORT_ONLY, (set_name, set(plants) & BACKPORT_ONLY)
        assert set(plants) <= KNOWN_PLANTS, (set_name, set(plants) - KNOWN_PLANTS)
        for name, occ in plants.items():
            assert isinstance(occ, int) and 0 < occ <= 32767, (set_name, name)  # paint.js passes Short.valueOf


# ------------------------------------------------------------------ 7. real data/regions.json

REAL_REGIONS = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
REAL_LANDMARKS = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
PRESET_KEYS = {"biome", "biome_bands", "terrain", "patches", "terrain_above", "terrain_below", "rock_slope_deg",
               "rock", "plants", "frost", "frost_above_y", "treeline_y"}


def _check_preset(name, pr):
    assert set(pr) <= PRESET_KEYS, (name, set(pr) - PRESET_KEYS)
    assert ("biome" in pr) != ("biome_bands" in pr), (name, "exactly one of biome / biome_bands")
    if "biome" in pr:
        assert pr["biome"] in PP.WP_BIOMES, (name, pr["biome"])
    else:
        bands = pr["biome_bands"]
        assert bands and bands[-1][0] is None, (name, "last band is open-topped")
        tops = [t for t, _ in bands[:-1]]
        assert all(isinstance(t, (int, float)) for t in tops) and tops == sorted(tops), (name, tops)
        for _, b in bands:
            assert b in PP.WP_BIOMES, (name, b)
    for key in ("terrain", "rock"):
        if key in pr:
            assert pr[key] in PP.TERRAIN_CODES, (name, key, pr[key])
    for patch in pr.get("patches") or []:
        assert patch["terrain"] in PP.TERRAIN_CODES and 0 <= patch["coverage"] <= 1, (name, patch)
    for key in ("terrain_above", "terrain_below"):
        for y, t in pr.get(key) or []:
            assert isinstance(y, (int, float)) and t in PP.TERRAIN_CODES, (name, key, y, t)
    if pr.get("treeline_y") is not None:
        ty = pr["treeline_y"]
        assert isinstance(ty, (int, float)) and not isinstance(ty, bool), (name, "treeline_y", ty)
    for pl in pr.get("plants") or []:
        assert pl["set"] in PP.PLANT_SETS and 0 <= pl["coverage"] <= 1, (name, pl)


# Removing this lets a preset typo (unknown biome, terrain, layer or plant set) crash a full 8192 paint run.
def test_real_presets_use_only_known_keys_and_names():
    presets = REAL_REGIONS["paint_presets"]
    assert presets
    for name, pr in presets.items():
        _check_preset(name, pr)


# Removing this lets a sub-region reference a missing preset/parent or collide on id, breaking paint and spawns.
def test_real_subregions_are_well_formed():
    presets = REAL_REGIONS["paint_presets"]
    region_ids = {r["id"] for r in REAL_REGIONS["regions"]}
    subs = REAL_REGIONS["subregions"]
    ids = [s["id"] for s in subs]
    assert len(ids) == len(set(ids)), "sub-region ids are unique"
    # rasterise_subregions stores 1-based indices in uint8
    assert len(subs) <= 255
    for s in subs:
        assert s["id"] and s["parent"] in region_ids, s.get("id")
        assert s["polygons"] and all(len(r) >= 3 for r in s["polygons"]), s["id"]
        assert s["encounters"]["table"] is None, s["id"]
        assert set(s["paint"]) <= {"preset", "override"}, s["id"]
        assert s["paint"]["preset"] in presets, (s["id"], s["paint"]["preset"])
        assert isinstance(s["measured"]["area_km2"], (int, float)), s["id"]
        if s["paint"].get("override"):
            _check_preset(s["id"], dict(presets[s["paint"]["preset"]], **s["paint"]["override"]))


# Removing this lets a landmark water body without an integer level or basin crash the lake pass.
def test_real_water_bodies_and_channels_are_readable():
    for lm in REAL_LANDMARKS["landmarks"]:
        wb = lm.get("water_body")
        if wb:
            assert isinstance(wb["level_y"], int), lm["id"]
            assert wb["basin_polygons"] and all(len(r) >= 3 for r in wb["basin_polygons"]), lm["id"]
        if lm.get("kind") == "river":
            for ax in lm.get("axes") or []:
                assert len(ax["polyline"]) >= 2, (lm["id"], ax.get("id"))
