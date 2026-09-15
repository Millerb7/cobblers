"""tools/paint_maps.py: region plan -> WorldPainter paint maps (manifest contract of tools/worldpainter/paint.js).

Runs on a 256x256 grid (PP.N monkeypatched) with a synthetic island heightmap and fixture regions/landmarks,
plus data checks on the real data/regions.json and data/landmarks.json.

Not covered: whether WorldPainter 2.27.1 accepts these maps (terrain names, plant names, biome ids, layer
behaviour on flooded columns) and what the exported world looks like. That needs a WorldPainter run and an
in-game look, recorded as an experiment; nothing here touches the real 8192x8192 heightmap.
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
HILL_C, HILL_TOP_R, HILL_R = (170, 128), 12, 50  # plateau y160, cone flanks down to y80
LAKE_C, LAKE_R, LAKE_FLOOR, LAKE_LEVEL = (80, 90), 12, 70, 75
LAKE_BASIN = [[64, 74], [96, 74], [96, 106], [64, 106]]
DRY_BASIN = [[100, 40], [120, 40], [120, 60], [100, 60]]  # all ground at y80, above its level
CREEK = [[60, 160], [110, 200]]

PRESETS = {
    "frosty_woods": {
        "biome": "minecraft:snowy_taiga", "terrain": "SNOW",
        "trees": [{"layer": "PineForest", "min": 4, "max": 12, "scale": 64, "max_y": 120}],
        "plants": [{"set": "grassland", "coverage": 0.5}],
        "frost": True,
    },
    "banded_hill": {
        "biome_bands": [[100, "minecraft:meadow"], [None, "minecraft:stony_peaks"]],
        "terrain": "GRASS",
        "trees": [{"layer": "DeciduousForest", "min": 2, "max": 10, "scale": 64, "max_y": 120}],
    },
}


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
    h = np.where(r_island <= ISLAND_R, 80.0, np.where(r_island <= ISLAND_R + 15, 50.0, 20.0)).astype(np.float32)
    r_hill = np.hypot(xx - HILL_C[0], zz - HILL_C[1])
    cone = 160.0 - (r_hill - HILL_TOP_R) * (80.0 / (HILL_R - HILL_TOP_R))
    h = np.where(r_hill <= HILL_TOP_R, 160.0, np.where(r_hill <= HILL_R, np.maximum(cone, 80.0), h))
    r_lake = np.hypot(xx - LAKE_C[0], zz - LAKE_C[1])
    h = np.where(r_lake <= LAKE_R, float(LAKE_FLOOR), h)
    return h.astype(np.float32)


WORLD = {"heightmap": {"sha256": "x"}, "vertical": {"sea_level": SEA}, "import": {"water_level": SEA}}


def _write_inputs(d, regions=None, landmarks=None):
    rp, lp = d / "regions.json", d / "landmarks.json"
    rp.write_text(json.dumps(regions if regions is not None else _regions()), encoding="utf-8")
    lp.write_text(json.dumps(landmarks if landmarks is not None else LANDMARKS), encoding="utf-8")
    return rp, lp


def _run_main(mp, d, regions=None, landmarks=None):
    mp.setattr(PP, "N", SMALL_N)
    heights = _heights()
    mp.setattr(PP.T, "load_from_args", lambda args: (heights.copy(), json.loads(json.dumps(WORLD))))
    rp, lp = _write_inputs(d, regions, landmarks)
    out = d / "paint"
    rc = PP.main(["--regions", str(rp), "--landmarks", str(lp), "--out", str(out), "--seed", "7", "--rivers", ""])
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
    with pytest.MonkeyPatch.context() as mp:
        rc, out, heights = _run_main(mp, d)
        # the real slope function, so the >35 degree rule is checked against what main() actually used
        slope = PP.T.slope_degrees(heights)
    maps = {p.name: np.asarray(Image.open(p)) for p in out.glob("*.png")}
    return {"rc": rc, "out": out, "h": heights, "slope": slope, "maps": maps,
            "manifest": json.loads((out / "manifest.json").read_text(encoding="utf-8")),
            "stats": json.loads((out / "stats.json").read_text(encoding="utf-8"))}


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
    for name in ("biomes.png", "terrain.png", "frost.png", "manifest.json", "stats.json",
                 "trees_PineForest.png", "trees_DeciduousForest.png", "plants_grassland.png",
                 "water_fixture_lake.png"):
        assert (out / name).is_file(), name


# Removing this lets a map be written as RGB/16-bit or misaligned, which paint.js reads as wrong levels.
def test_full_maps_are_8bit_grayscale_full_grid(painted):
    for p in painted["out"].glob("*.png"):
        img, arr = _png(p)
        assert img.mode == "L", p.name
        assert arr.dtype == np.uint8, p.name
        if not p.name.startswith("water_"):
            assert arr.shape == (SMALL_N, SMALL_N), p.name


# Removing this lets values outside what paint.js maps (0-15 trees, 0/1 masks) reach WorldPainter.
def test_map_value_ranges_match_paint_js(painted):
    m = painted["maps"]
    for k in PP.TREE_LAYERS:
        assert m["trees_%s.png" % k].max() <= 15
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
    layers = [t["layer"] for t in man["trees"]]
    assert layers == [k for k in PP.TREE_LAYERS if m["trees_%s.png" % k].any()]
    assert set(layers) == {"PineForest", "DeciduousForest"}
    for t in man["trees"]:
        assert t["map"] == "trees_%s.png" % t["layer"] and t["layer"] in PP.TREE_LAYERS
    names = [p["name"] for p in man["plants"]]
    assert names == ["cobblers_grassland"]
    assert man["plants"][0]["map"] == "plants_grassland.png"
    assert man["plants"][0]["plants"] == PP.PLANT_SETS["grassland"]
    assert man["biomes"] == "biomes.png" and man["terrain"] == "terrain.png" and man["frost"] == "frost.png"
    assert {int(k): v for k, v in man["terrain_codes"].items()} == {v: k for k, v in PP.TERRAIN_CODES.items()}
    assert man["source"]["heightmap_sha256"] == "x" and man["source"]["seed"] == 7


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


# Removing this lets trees grow on cliffs, above the treeline, in lakes and on creek beds.
def test_tree_density_zero_where_forbidden(painted):
    m, h, slope = painted["maps"], painted["h"], painted["slope"]
    basin = _mask(LAKE_BASIN) & (h < LAKE_LEVEL + 2)
    creek = _line_mask(CREEK) & (h >= SEA)
    assert (slope > 35).any() and (h > 120 + JITTER).any() and basin.any() and creek.any()
    for k in PP.TREE_LAYERS:
        t = m["trees_%s.png" % k]
        assert (t[slope > 35] == 0).all(), k
        assert (t[h > 120 + JITTER] == 0).all(), k  # both fixture presets use max_y 120
        assert (t[basin] == 0).all(), k
        assert (t[creek] == 0).all(), k
    # positive control: flat woods land away from those rules does carry trees (min density 4)
    hill, woods = _sub_masks()
    from PIL import ImageFilter
    near_creek = np.asarray(Image.fromarray(_line_mask(CREEK).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    ok = woods & (h == 80) & (slope < 1) & ~_mask(LAKE_BASIN) & ~near_creek
    assert ok.any() and (m["trees_PineForest.png"][ok] >= 4).all()


# Removing this lets tree layers be painted on the seabed wherever a sub-region polygon overhangs the coast.
def test_tree_density_zero_on_sea(painted):
    sea = painted["h"] < SEA
    for k in PP.TREE_LAYERS:
        assert (painted["maps"]["trees_%s.png" % k][sea] == 0).all(), k


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

# Names from org.pepsoft.worldpainter.layers.plants.Plants already vetted in PLANT_SETS; extend deliberately.
KNOWN_PLANTS = {
    "Tall Grass", "Fern", "Dandelion", "Poppy", "Oxeye Daisy", "Cornflower", "Azure Bluet", "Allium",
    "Pink Tulip", "Peony", "Lilac", "White Tulip", "Sweet Berry Bush", "Azalea", "Flowering Azalea",
    "Large Fern", "Dead Shrub", "Blue Orchid", "Brown Mushroom", "Red Mushroom",
}


# Removing this lets "Short Grass" back in: WorldPainter 2.27.1 writes minecraft:grass, invalid in 1.21.1.
def test_plant_sets_use_known_names_and_no_short_grass():
    for set_name, plants in PP.PLANT_SETS.items():
        assert "Short Grass" not in plants, set_name
        assert set(plants) <= KNOWN_PLANTS, (set_name, set(plants) - KNOWN_PLANTS)
        for name, occ in plants.items():
            assert isinstance(occ, int) and 0 < occ <= 32767, (set_name, name)  # paint.js passes Short.valueOf


# ------------------------------------------------------------------ 7. real data/regions.json

REAL_REGIONS = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
REAL_LANDMARKS = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
PRESET_KEYS = {"biome", "biome_bands", "terrain", "patches", "terrain_above", "terrain_below", "rock_slope_deg",
               "rock", "trees", "plants", "frost", "frost_above_y"}


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
    for tr in pr.get("trees") or []:
        assert tr["layer"] in PP.TREE_LAYERS, (name, tr)
        assert 0 <= tr["min"] <= tr["max"] <= 15, (name, tr)
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
