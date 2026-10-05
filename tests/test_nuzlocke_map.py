"""tools/nuzlocke_map.py: area building and per-segment selection, on a hand-made fixture (no pack, no heightmap)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nuzlocke_map as N  # noqa: E402


def spawn(sid, pokemon, box, bucket="common", level="5-9", where="grounded", **cond):
    c = {"minX": box[0], "maxX": box[1], "minZ": box[2], "maxZ": box[3]}
    c.update(cond)
    return {"id": sid, "pokemon": pokemon, "type": "pokemon", "spawnablePositionType": where, "bucket": bucket,
            "level": level, "weight": 1.0, "condition": c}


def doc(*spawns):
    return {"enabled": True, "spawns": list(spawns)}


# A line walking east along z=0 from x=0 to x=999. Areas laid along it:
#   meadow  x 0-199 (corridor stretch) + 200-249 (its own file)   entered at 0, 250 blocks
#   wood    x 300-699                                              entered at 300, 400 blocks
#   pond    water only, x 720-739                                  entered at 720, 20 blocks
#   ridge   x 800-999                                              entered at 800, 200 blocks
#   near    off the line, 100 blocks north                         a detour within 300
#   far     off the line, 450 blocks north                         a detour only within 600
PACK = {
    ("routes", "route_01_a_to_b"): doc(
        spawn("r01_b0000_meadow_pidgey", "pidgey", (0, 199, -5, 5)),
        spawn("r01_b0001_p0_wood_oddish", "oddish", (300, 699, -5, 5), bucket="uncommon", level="7-12"),
        spawn("r01_b0002_ridge_vulpix_alolan", "vulpix_alolan", (800, 999, -5, 5), bucket="rare"),
    ),
    ("subregions", "meadow"): doc(
        spawn("meadow_b0000_pidgey", "pidgey", (200, 249, -5, 5)),
        spawn("meadow_b0000_hoppip", "hoppip", (200, 249, -5, 5), bucket="ultra-rare", timeRange="night"),
        spawn("meadow_h0000_dubwool", "dubwool alpha=true", (220, 230, -50, -40), level="30-30"),
    ),
    ("subregions", "pond"): doc(spawn("pond_b0000_magikarp", "magikarp", (720, 739, -5, 5), where="submerged")),
    ("subregions", "near"): doc(spawn("near_b0000_ekans", "ekans", (500, 520, 100, 120))),
    ("subregions", "far"): doc(spawn("far_b0000_zubat", "zubat", (500, 520, 450, 470))),
}
LINE = np.array([(x, 0) for x in range(1000)])


def areas():
    return N.build_areas(PACK, {"meadow": "Meadow"}, {"route_01_a_to_b": "Route 1"})


def ids(picks):
    return [p["id"] for p in picks]


def test_a_corridor_stretch_and_its_subregion_are_one_area():
    a = areas()
    assert set(a) == {"sub/meadow", "sub/wood", "sub/pond", "sub/ridge", "sub/near", "sub/far"}
    m = a["sub/meadow"]
    assert m["name"] == "Meadow" and m["routes"] == ["Route 1"]
    assert {tuple(b) for b in m["boxes"]} == {(0, 199, -5, 5), (200, 249, -5, 5)}
    # the heart is not a first-encounter entry and adds no box
    assert all("_h0000_" not in e["id"] for e in m["entries"]) and len(m["hearts"]) == 1
    # a species name holding an underscore still parses out of a route id
    assert a["sub/ridge"]["entries"][0]["pokemon"] == "vulpix_alolan"


def test_summary_buckets_tags_bosses_and_water():
    a = areas()
    sm = N.summarise(a["sub/meadow"])
    assert sm["levels"] == (5, 9)
    assert sm["groups"]["common"] == [("Pidgey", [])]
    assert sm["groups"]["ultra-rare"] == [("Hoppip", ["night", "off path"])]
    assert sm["bosses"] == ["Dubwool"] and not sm["water_only"]
    assert N.summarise(a["sub/pond"])["water_only"]


def test_on_path_areas_come_in_travel_order():
    picks = N.select_segment(LINE, areas(), lo=4, hi=6, detour=300, detour_max=None,
                             reserved={"sub/meadow", "sub/wood", "sub/pond", "sub/ridge"})
    assert ids(picks) == ["sub/meadow", "sub/wood", "sub/pond", "sub/ridge"]
    assert [p["index"] for p in picks] == [0, 300, 720, 800]
    assert [p["blocks"] for p in picks] == [250, 400, 20, 200]
    assert not any(p["detour"] for p in picks)


def test_over_the_maximum_keeps_the_most_walked_in_travel_order():
    picks = N.select_segment(LINE, areas(), lo=1, hi=2, detour=300)
    assert ids(picks) == ["sub/meadow", "sub/wood"]   # 250 and 400 blocks beat ridge 200 and pond 20
    picks = N.select_segment(LINE, areas(), lo=1, hi=3, detour=300)
    assert ids(picks) == ["sub/meadow", "sub/wood", "sub/ridge"]


def test_short_segments_take_the_nearest_detours_then_the_far_reach():
    a = areas()
    used = {"sub/meadow", "sub/wood"}
    picks = N.select_segment(LINE, a, used=used, lo=4, hi=6, detour=300, detour_max=None)
    assert ids(picks) == ["sub/near", "sub/pond", "sub/ridge"]   # far is 450 off: out of reach
    near = picks[0]
    assert near["detour"] and near["dist"] == 100 and near["at"] == (500, 100) and near["index"] == 500
    picks = N.select_segment(LINE, a, used=used, lo=4, hi=6, detour=300, detour_max=600)
    assert ids(picks) == ["sub/far", "sub/near", "sub/pond", "sub/ridge"] or \
        ids(picks) == ["sub/near", "sub/far", "sub/pond", "sub/ridge"]
    assert {p["id"]: p["dist"] for p in picks if p["detour"]} == {"sub/near": 100, "sub/far": 450}


def test_a_detour_never_takes_an_area_another_segment_walks_through():
    short = LINE[:250]    # meadow only
    picks = N.select_segment(short, areas(), lo=3, hi=6, detour=300, detour_max=None, reserved={"sub/wood"})
    assert "sub/wood" not in ids(picks)
    assert ids(picks)[0] == "sub/meadow"
    picks = N.select_segment(short, areas(), lo=3, hi=6, detour=300, detour_max=None, reserved=())
    assert "sub/wood" in ids(picks)


def test_spread_separates_markers():
    pts = N.spread([(100, 100), (100, 100), (150, 120), (5000, 5000)], gap=180)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            assert np.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) >= 178
    assert pts[3] == (5000, 5000)
