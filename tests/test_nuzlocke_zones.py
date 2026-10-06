"""data/nuzlocke_zones.json and tools/nuzlocke_zones.py: one catch zone per distinct encounter table a player can meet.

The zone rule is checked against the inputs it claims, not against the generator's own intermediate values.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nuzlocke_zones as NZ  # noqa: E402


def doc():
    return json.loads((ROOT / "data" / "nuzlocke_zones.json").read_text(encoding="utf-8"))


def data(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def test_the_file_is_what_the_generator_writes_today():
    assert NZ.dumps(NZ.build()) == (ROOT / "data" / "nuzlocke_zones.json").read_text(encoding="utf-8"), \
        "data/nuzlocke_zones.json is stale: python tools/nuzlocke_zones.py"


def test_every_encounter_table_is_a_zone_or_a_named_exclusion():
    d = doc()
    tables = set(data("encounter_design.json")["tables"])
    land = {z["zone"] for z in d["zones"] if z["kind"] == "land"}
    excluded = {n["zone"] for n in d["not_zones"] if n["what"] == "sub-region table"}
    assert land | excluded == tables and not land & excluded
    # the sea bands and waterways with an ambient roster
    spawns = data("spawns.json")
    rostered = {e["scope"] for e in spawns["entries"] if e.get("ambient") and e.get("weight", 0) > 0}
    bands = {b["id"] for m in spawns["marine_zones"] for b in m["bands"]} & rostered
    assert bands == {z["zone"] for z in d["zones"] if z["kind"] == "sea"}
    ways = {w["id"] for w in data("waterways.json")["waterways"]} & rostered
    assert ways == {z["zone"] for z in d["zones"] if z["kind"] == "waterway"}


def test_a_route_leg_is_not_a_table_of_its_own():
    # recomputed from the inputs: every species a corridor carries is in a table of a sub-region the leg crosses
    spawns = data("spawns.json")
    sub = {x["id"]: {e["pokemon"] for e in x["entries"]} for x in spawns["subregions"]}
    for r in data("routes.json")["routes"]:
        crossed = r["geography"]["subregions"]
        chosen = set(spawns["route_species_selection"][r["id"]]["species"])
        assert len(crossed) >= 2, r["id"]
        assert chosen <= set().union(*(sub[c] for c in crossed)), r["id"]


def test_victory_roads_six_zones_are_its_placed_pools_cores_folded_in():
    d = doc()
    caves = {z["zone"]: z for z in d["zones"] if z["kind"] == "cave"}
    assert set(caves) == {"vr_" + z["id"] for z in data("vr_caves.json")["zones"]}
    placed = {}
    for b in data("habitat_blocks.json")["blocks"]:
        if b.get("status") == "placed" and b["pool"].startswith("cobblers:vrc_"):
            placed[b["pool"][9:]] = placed.get(b["pool"][9:], 0) + 1
    assert sum(z["blocks"] for z in caves.values()) == sum(placed.values())
    assert caves["vr_the_dark"]["pools"] == ["vrc_cave"]          # tools/vr_caves.py's one irregular name


def test_legs_mark_each_land_zone_new_once():
    d = doc()
    land = {z["zone"] for z in d["zones"] if z["kind"] == "land"}
    news = [o["zone"] for leg in d["legs"] for o in leg["zones"] if o["new"]]
    assert len(news) == len(set(news))
    assert set(news) <= land
    assert [leg["route"] for leg in d["legs"]] == [r["id"] for r in sorted(data("routes.json")["routes"],
                                                                             key=lambda r: int(r["order"]))]


def test_every_zone_has_a_title_name_and_unique_id():
    zones = doc()["zones"]
    assert len({z["zone"] for z in zones}) == len(zones)
    assert not [z["zone"] for z in zones if not z["name"] or not z["subtitle"]]


def _mask(poly, xs, zs):
    """Even-odd point-in-polygon over a grid, written here rather than taken from the generator's helper."""
    X, Z = np.meshgrid(xs, zs)
    inside = np.zeros(X.shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % n]
        cross = ((z1 > Z) != (z2 > Z)) & (X < (x2 - x1) * (Z - z1) / ((z2 - z1) or 1e-9) + x1)
        inside ^= cross
    return inside


def test_an_excluded_sub_region_is_under_the_sea_at_every_sampled_column():
    import ground as G
    g = G.load()
    sea = data("world.json")["vertical"]["sea_level"]
    subs = {s["id"]: s for s in data("regions.json")["subregions"]}
    excluded = [n["zone"] for n in doc()["not_zones"] if n["what"] == "sub-region table"]
    assert excluded, "no sunk sub-region: drop this test or the exclusion rule"
    for sid in excluded:
        for poly in subs[sid]["polygons"]:
            xs = np.arange(min(p[0] for p in poly), max(p[0] for p in poly) + 1, 4)
            zs = np.arange(min(p[1] for p in poly), max(p[1] for p in poly) + 1, 4)
            m = _mask(poly, xs, zs)
            h = np.round(g.heights[np.ix_(zs - g.oz, xs - g.ox)])
            assert m.any() and h[m].max() < sea, sid


PACK = ROOT / "build" / "datapacks" / "cobblers_spawns"


@pytest.mark.skipif(not PACK.is_dir(), reason="no compiled spawn pack in build/ (python tools/compile_spawns.py)")
def test_the_zones_are_the_compiled_packs_areas():
    problems, n = NZ.audit(PACK)
    assert n > 60
    assert not [p for p in problems if not p.startswith("KNOWN")], problems
