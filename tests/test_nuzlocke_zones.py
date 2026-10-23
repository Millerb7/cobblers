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
    if not excluded:
        # NOT_EXECUTED, not passed: the only two sunk sub-regions were the Jungle Isle's (jungle_west, jungle_east), removed from
        # data/regions.json on 2026-10-21 when the island's bank became Pacifidlog Waters. The exclusion rule in
        # tools/nuzlocke_zones.py is idle until a sub-region sinks again; this test runs again the day one does.
        pytest.skip("no sub-region is under the sea: the exclusion rule has nothing to exclude")
    for sid in excluded:
        for poly in subs[sid]["polygons"]:
            xs = np.arange(min(p[0] for p in poly), max(p[0] for p in poly) + 1, 4)
            zs = np.arange(min(p[1] for p in poly), max(p[1] for p in poly) + 1, 4)
            m = _mask(poly, xs, zs)
            h = np.round(g.heights[np.ix_(zs - g.oz, xs - g.ox)])
            assert m.any() and h[m].max() < sea, sid


# ------------------------------------------------------------------------------------------------ legendaries, dungeons
# The owner, 2026-10-23: "nuzlocke page should show dungeons and legendaries per area, so a player can count those" and
# "just dungeon name ... i have 1 encounter no matter the level".


def _inside(poly, x, z):
    hit = False
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % len(poly)]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            hit = not hit
    return hit


def _zone_at(x, z):
    """The sub-region holding the column: even-odd over data/regions.json polygons, written here."""
    return next(s["id"] for s in data("regions.json")["subregions"] if any(_inside(p, x, z) for p in s["polygons"]))


def row_problems(by_zone):
    """What an independent reading of the sources says the register must hold and does not: every sited chamber and
    grotto of data/legendaries.json and every sanctuary occupant, in the zone its own coordinate falls in."""
    have = {(zone, r["species"]) for zone, rows in by_zone.items() for r in rows}
    out = []
    for r in data("legendaries.json")["encounters"]:
        if r["status"] == "sited":
            at = r["mouth"] if r["kind"] == "lake_grotto" else r["portal"]
            if (_zone_at(*at), r["species"]) not in have:
                out.append("%s is not a row of %s" % (r["species"], _zone_at(*at)))
    for s in data("sanctuaries.json")["sanctuaries"]:
        o = s["occupant"]
        for sp in [o["species"]] + list(o.get("co_occupants") or []):
            if (_zone_at(*s["site"]["centre"]), sp) not in have:
                out.append("%s is not a row of %s" % (sp, _zone_at(*s["site"]["centre"])))
    return out


def test_the_file_holds_the_legendaries_the_sources_place():
    d = doc()
    by_zone = {z["zone"]: z["legendaries"] for z in d["zones"] if z.get("legendaries")}
    assert not row_problems(by_zone)
    assert d["counts"]["legendaries"] == sum(len(v) for v in by_zone.values()) > 40
    assert all(z["zone"] in {y["zone"] for y in d["zones"]} for z in d["zones"] if z.get("legendaries"))
    # no row appears twice in a zone, and a dungeon's own legendary is not also a row
    for rows in by_zone.values():
        assert len({r["species"] for r in rows}) == len(rows)
    held = set(d["legendary_register"]["dungeon_held"])
    assert not held & {r["species"] for rows in by_zone.values() for r in rows}


def test_the_register_says_what_it_does_not_cover():
    reg = doc()["legendary_register"]
    assert len(reg["not_covered"]) >= 4 and "Our list is not the world" in " ".join(reg["not_covered"])
    assert {e["species"] for e in reg["excluded"]} >= {"lugia", "entei", "mewtwo"}
    assert any("lugia" == n["species"] for n in reg["not_placed"]) or any("lugia" == e["species"] for e in reg["excluded"])


def test_each_dungeon_is_one_zone_by_its_player_facing_name():
    d = doc()
    want = [(x["id"], x["name"]) for x in data("dungeons.json")["dungeons"]]
    assert [(x["dungeon"], x["name"]) for x in d["dungeons"]] == want
    assert d["counts"]["dungeons"] == len(want) >= 13
    assert len({x["zone"] for x in d["dungeons"]}) == len(want)
    assert not {x["zone"] for x in d["dungeons"]} & {z["zone"] for z in d["zones"]}, "a dungeon id is also an area id"
    assert "Night Shift" in " ".join(n for _i, n in want)


def test_a_generator_mutation_is_caught_by_the_independent_reading(monkeypatch):
    """Mutate the CODE, leave the data alone (CLAUDE.md 'How to prove an audit is independent'): a locator that puts every
    column in the wrong zone, a footprint centre moved 3,000 blocks, and a dungeon list that loses one must each make the
    independent reading above report a problem (or stop the build)."""
    zones = doc()["zones"]
    by_zone, _ = NZ.legendary_register(zones)
    assert not row_problems(by_zone), "the unmutated generator already disagrees with the sources"
    ids = [z["zone"] for z in zones if z["kind"] == "land"]
    monkeypatch.setattr(NZ.Locator, "zone", lambda self, x, z: ids[(x + z) % len(ids)])
    wrong, _ = NZ.legendary_register(zones)
    assert row_problems(wrong), "a locator that scatters the columns went unnoticed"
    monkeypatch.undo()
    import adopted_sites as A
    real = A.centre
    monkeypatch.setattr(A, "centre", lambda s, placements=None: [real(s, placements)[0] + 3000, real(s, placements)[1]])
    try:
        moved, _ = NZ.legendary_register(zones)
    except SystemExit:
        moved = None                       # a column outside every zone stops the build: also caught
    if moved is not None:
        assert {(z, r["species"]) for z, rows in moved.items() for r in rows} != \
            {(z, r["species"]) for z, rows in by_zone.items() for r in rows}, "moving the sites changed no row"
    monkeypatch.undo()
    real_load = NZ.load
    monkeypatch.setattr(NZ, "load", lambda n: dict(real_load(n), dungeons=real_load(n)["dungeons"][1:]) if n == "dungeons.json" else real_load(n))
    assert len(NZ.dungeons()) == len(data("dungeons.json")["dungeons"]) - 1, "the mutation did not apply"
    assert [x["name"] for x in NZ.dungeons()] != [x["name"] for x in doc()["dungeons"]]


def test_a_site_with_no_species_entry_stops_the_build(monkeypatch):
    """SITE_SPECIES types the species of an adopted site; a site that is added without one must not pass silently."""
    zones = doc()["zones"]
    mutated = dict(NZ.SITE_SPECIES)
    mutated.pop("adopted_mew_temple")
    monkeypatch.setattr(NZ, "SITE_SPECIES", mutated)
    with pytest.raises(SystemExit):
        NZ.legendary_register(zones)
    monkeypatch.setattr(NZ, "SITE_SPECIES", dict(NZ.SITE_SPECIES, adopted_mew_temple=["mewtwo"]))
    with pytest.raises(SystemExit):
        NZ.legendary_register(zones)


PACK = ROOT / "build" / "datapacks" / "cobblers_spawns"


@pytest.mark.skipif(not PACK.is_dir(), reason="no compiled spawn pack in build/ (python tools/compile_spawns.py)")
def test_the_zones_are_the_compiled_packs_areas():
    problems, n = NZ.audit(PACK)
    assert n > 60
    assert not [p for p in problems if not p.startswith("KNOWN")], problems
