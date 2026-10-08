"""tools/spawn_habitat_audit.py: wrong-country spawns (the owner, 2026-10-04).

The synthetic tests build a tiny Cobblemon jar, a tiny regions file and a tiny compiled pack whose every verdict can
be worked out by hand from the climate ladder (cold 0, cool 1, temperate 2, warm/arid 3; a fit is one step). The
real-data tests compile the pack from the committed data into a temporary folder and judge it against the Cobblemon
1.8 jar; they skip when no jar is found. The mutation test changes the GENERATOR (tools/build_encounters.py's
drop_stages), never the data, and shows the audit catching Crabominable again.

Not covered: whether any of these species actually spawns in game (validity, not behaviour), and the Victory Road
Habitat pools (the audit judges spawn_pool_world only).
"""
from __future__ import annotations

import json
import shutil
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import spawn_habitat_audit as A  # noqa: E402


# ------------------------------------------------------------------------------------------- synthetic fixture
def _spawn(pokemon, biomes, pos="grounded", **cond):
    c = dict(cond)
    if biomes is not None:
        c["biomes"] = biomes
    return {"id": pokemon.replace(" ", "-") + "-1", "pokemon": pokemon, "presets": ["natural"], "type": "pokemon",
            "spawnablePositionType": pos, "bucket": "common", "level": "5-30", "weight": 10.0, "condition": c}


def _species(name, types_, eggs=("field",), evolves_to=None, forms=()):
    d = {"name": name.title(), "primaryType": types_[0], "eggGroups": list(eggs), "forms": list(forms),
         "evolutions": [{"id": "x", "variant": "level_up", "result": evolves_to}] if evolves_to else []}
    if len(types_) > 1:
        d["secondaryType"] = types_[1]
    return d


def make_jar(path):
    tags = {
        "is_peak": ["minecraft:jagged_peaks", {"id": "terralith:emerald_peaks", "required": False}],
        "is_beach": ["#minecraft:is_beach"],
        "is_coast": ["minecraft:stony_shore", "#cobblemon:is_beach"],
        "is_desert": ["minecraft:desert"],
        "is_arid": ["#cobblemon:is_desert", "#minecraft:is_savanna"],
        "is_snowy": ["minecraft:snowy_plains"],
        "is_sea": ["minecraft:frozen_ocean", "minecraft:ocean"],
        "is_lush": ["minecraft:lush_caves"],
        "is_volcanic": [{"id": "wythers:volcano", "required": False}],
    }
    species = {
        "crab": _species("crab", ["fighting"], evolves_to="icecrab"),
        "icecrab": _species("icecrab", ["fighting", "ice"]),
        "shrew": _species("shrew", ["ground"], forms=[{"name": "Alola", "aspects": ["alolan"], "primaryType": "ice"}]),
        "seal": _species("seal", ["ice", "water"], eggs=("water_1", "field")),
        "firefox": _species("firefox", ["fire"]),
        "leafmon": _species("leafmon", ["grass"], evolves_to="leafmon2"),
        "leafmon2": _species("leafmon2", ["grass"]),
        "caveling": _species("caveling", ["rock"]),
        "frostling": _species("frostling", ["ice"]),
        "digger": _species("digger", ["ground"]),
        "lavaling": _species("lavaling", ["fire"]),
    }
    spawns = {
        "0001_crab": [_spawn("crab", ["#cobblemon:is_coast"])],
        "0002_icecrab": [_spawn("icecrab", ["#cobblemon:is_peak"])],
        "0003_shrew": [_spawn("shrew", ["#cobblemon:is_arid"]), _spawn("shrew alolan", ["#cobblemon:is_snowy"])],
        "0004_seal": [_spawn("seal", ["#cobblemon:is_sea"], pos="submerged")],     # cold and temperate SEA
        "0005_firefox": [_spawn("firefox", ["#cobblemon:is_desert"])],
        "0006_leafmon": [_spawn("leafmon", ["#cobblemon:is_desert"])],
        "0008_leafmon2": [_spawn("leafmon2", ["#cobblemon:is_desert"])],
        "0007_caveling": [_spawn("caveling", ["#cobblemon:is_lush"])],
        # frostling has no spawn file at all: judged by type (ice)
        "0009_digger": [_spawn("digger", ["#cobblemon:is_desert"]),
                        _spawn("digger", ["#cobblemon:is_desert"], canSeeSky=False)],
        "0010_lavaling": [_spawn("lavaling", ["#cobblemon:is_volcanic"])],
    }
    with zipfile.ZipFile(path, "w") as z:
        for t, values in tags.items():
            z.writestr("data/cobblemon/tags/worldgen/biome/%s.json" % t, json.dumps({"values": values}))
        for n, d in species.items():
            z.writestr("data/cobblemon/species/generation1/%s.json" % n, json.dumps(d))
        for n, s in spawns.items():
            z.writestr("data/cobblemon/spawn_pool_world/%s.json" % n, json.dumps({"enabled": True, "spawns": s}))
        z.writestr("data/cobblemon/spawn_detail_presets/natural.json", json.dumps({"condition": {}}))
    return path


def _square(x0, z0, size):
    return [[[x0, z0], [x0 + size, z0], [x0 + size, z0 + size], [x0, z0 + size]]]


def _sub(sid, preset, x0, z0, coast=False, p10=100):
    b = [{"basis": "painted change of cover (treeline, snowline or ground)", "neighbour": "x"}]
    if coast:
        b.append({"basis": "coast", "neighbour": None})
    return {"id": sid, "parent": "land", "paint": {"preset": preset}, "boundaries": b,
            "measured": {"elevation": {"p10": p10}}, "polygons": _square(x0, z0, 100)}


def make_regions():
    subs = [
        _sub("strand", "coast_scrub", 0, 0, coast=True),          # temperate; coast 10 blocks from the sea: sea
        _sub("peak", "alpine_peaks", 1000, 0),                    # cold
        _sub("lake", "plains", 2000, 0, coast=True),              # temperate; a coast 1,800 blocks from the sea: a lake
        _sub("dunes", "desert", 3000, 0),                         # arid
        _sub("woods", "taiga_dense", 4000, 0),                    # cool
        _sub("isle", "plains", 5000, 0, coast=True),              # temperate; an island: sea
    ]
    return {
        "geometry": {"polygon_tolerance_blocks": 24},
        "paint_presets": {p: {} for p in ("coast_scrub", "alpine_peaks", "plains", "desert", "taiga_dense")},
        "regions": [{"id": "land", "region_class": "terrain", "subregions": [s["id"] for s in subs[:5]]},
                    {"id": "an_isle", "region_class": "island", "subregions": ["isle"]}],
        "subregions": subs,
        "marine_regions": [{"id": "north_sea", "climate": {"temperature": "cold"},
                            "polygons": [[[-200, -500], [200, -500], [200, -10], [-200, -10]]]}],
    }


MARINE_SPAWNS = {"marine_zones": [{"id": "zone", "marine_region": "north_sea", "bands": [{"id": "north_band"}]}]}
WATERWAYS = {"waterways": [{"id": "creek", "polyline": [[4010, 10], [4050, 50]]}]}       # inside "woods" only

DOC = """# design

## 11. The mainline starters in the wild (the owner, 2026-10-02)

| Leg | Family: table (how) |
|---|---|
| 1 | Leafmon: the woods (find). |

## 12. next
"""


def entry(eid, pokemon, pos="grounded", **cond):
    return {"id": eid, "pokemon": pokemon, "type": "pokemon", "spawnablePositionType": pos, "bucket": "common",
            "level": "5-9", "weight": 1.0, "condition": dict({"minX": 0, "maxX": 1, "minZ": 0, "maxZ": 1}, **cond)}


SUB_ENTRIES = {
    "strand": [entry("strand_b0000_crab", "crab"), entry("strand_b0001_icecrab", "icecrab"),
               entry("strand_b0002_seal", "seal", pos="submerged")],
    "peak": [entry("peak_b0000_shrew", "shrew"), entry("peak_b0001_shrew_alolan", "shrew alolan"),
             entry("peak_b0002_caveling", "caveling"), entry("peak_b0003_digger", "digger"),
             entry("peak_b0004_digger", "digger", maxY=40), entry("peak_b0005_firefox", "firefox",
                                                                     biomes=["minecraft:desert"])],
    "lake": [entry("lake_b0000_seal", "seal", pos="submerged"), entry("lake_b0001_firefox", "firefox")],
    "dunes": [entry("dunes_b0000_frostling", "frostling"), entry("dunes_b0001_lavaling", "lavaling")],
    "woods": [entry("woods_b0000_firefox", "firefox"), entry("woods_b0001_leafmon2", "leafmon2"),
              entry("woods_h0000_leafmon2", "leafmon2")],
    "isle": [entry("isle_b0000_seal", "seal", pos="submerged")],
}
ROUTE_ENTRIES = [entry("r01_b0000_strand_icecrab", "icecrab"), entry("r01_b0001_peak_shrew", "shrew")]


def make_pack(root, sub_entries=SUB_ENTRIES, extra=None):
    base = root / "data" / "cobblers" / "spawn_pool_world"
    for sub, spawns in sub_entries.items():
        (base / "subregions").mkdir(parents=True, exist_ok=True)
        (base / "subregions" / ("%s.json" % sub)).write_text(json.dumps({"spawns": spawns}), encoding="utf-8")
    (base / "routes").mkdir(parents=True, exist_ok=True)
    (base / "routes" / "r01.json").write_text(json.dumps({"spawns": ROUTE_ENTRIES}), encoding="utf-8")
    (base / "marine").mkdir(parents=True, exist_ok=True)
    (base / "marine" / "north_band.json").write_text(json.dumps({"spawns": [
        entry("north_band_b0000_seal", "seal", pos="submerged"),
        entry("north_band_b0001_firefox", "firefox", pos="surface")]}), encoding="utf-8")
    (base / "waterways").mkdir(parents=True, exist_ok=True)
    (base / "waterways" / "creek.json").write_text(json.dumps({"spawns": [
        entry("creek_b0000_firefox", "firefox", neededNearbyBlocks=["minecraft:water"])]}), encoding="utf-8")
    for (kind, name), spawns in (extra or {}).items():
        (base / kind / ("%s.json" % name)).write_text(json.dumps({"spawns": spawns}), encoding="utf-8")
    return root


@pytest.fixture()
def synthetic(tmp_path):
    jar = A.Jar(make_jar(tmp_path / "fake-cobblemon.jar"))
    pack = make_pack(tmp_path / "pack")

    def run(known=None, regions=None, pack_dir=pack):
        rows, stale = A.audit(pack_dir, jar, regions or make_regions(), WATERWAYS, MARINE_SPAWNS, DOC,
                              known=known or {}, starter_families=1)
        return {(r["place_id"], r["species"], json.dumps(r["conditions"], sort_keys=True)): r for r in rows}, stale
    return run, jar, tmp_path


def cls(rows, place, species, **cond):
    """The class of one entry group; `cond` is its habitat conditions (the box keys are not part of the group)."""
    return rows[(place, species, json.dumps(cond, sort_keys=True))]["class"]


# ------------------------------------------------------------------------------------------- climate ladder
def test_climate_ladder_one_step_fits_two_steps_do_not():
    # without it a cold-native on a temperate strand (two steps) could be called a fit, which is the owner's complaint
    assert A.distance("cold", "cool") == 1 and A.distance("cool", "temperate") == 1
    assert A.distance("temperate", "warm") == 1 and A.distance("temperate", "arid") == 1
    assert A.distance("warm", "arid") == 1
    assert A.distance("cold", "temperate") == 2 and A.distance("cool", "arid") == 2
    assert A.distance("cold", "arid") == 3 and A.distance("cold", "warm") == 3


def test_every_real_paint_preset_has_a_climate():
    # without it a new preset would make every place painted with it unjudgeable (Places fails closed on it)
    regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    assert set(regions["paint_presets"]) <= set(A.PRESET_CLIMATE)


def test_unknown_preset_fails_closed(synthetic):
    # without it a preset missing from the table would silently judge nothing
    run, _jar, _ = synthetic
    regions = make_regions()
    regions["paint_presets"]["volcano_new"] = {}
    with pytest.raises(A.AuditError, match="volcano_new"):
        run(regions=regions)


# ------------------------------------------------------------------------------------------- verdicts by hand
def test_cold_native_evolution_on_a_temperate_strand_is_a_misfit(synthetic):
    # the Crabominable case: the base fits the coast, its peak-only evolution does not; losing this check loses it
    rows, _ = synthetic[0]()
    assert cls(rows, "strand", "crab") == "FIT"                        # stony shore cool, beach temperate
    assert cls(rows, "strand", "icecrab") == "MISFIT"                  # jagged peaks cold: two steps from temperate


def test_route_entries_are_judged_in_the_sub_region_their_id_names(synthetic):
    # without it a corridor entry would escape the sweep; r01's icecrab joins the strand group (2 compiled entries)
    rows, _ = synthetic[0]()
    key = ("strand", "icecrab", json.dumps({}, sort_keys=True))
    assert rows[key]["entries"] == 2
    assert rows[("peak", "shrew", "{}")]["entries"] == 2


def test_regional_forms_are_judged_apart(synthetic):
    # without it Alolan Sandshrew (snowy) would excuse plain Sandshrew (arid) on a snowy mountain, or the reverse
    rows, _ = synthetic[0]()
    assert cls(rows, "peak", "shrew") == "MISFIT"                      # arid, three steps from cold
    assert cls(rows, "peak", "shrew alolan") == "FIT"                  # snowy plains, cold


def test_sea_species_in_a_lake_is_a_misfit_and_fits_the_sea(synthetic):
    # the Wailord/Shellos case: a sea-only species in fresh water; the climate alone would let it through
    rows, _ = synthetic[0]()
    assert cls(rows, "lake", "seal") == "MISFIT"                       # coast boundary, but 1,800 blocks from the sea
    assert cls(rows, "strand", "seal") == "FIT"                        # coast 10 blocks from the sea polygon
    assert cls(rows, "isle", "seal") == "FIT"                          # an island's coast is the sea
    assert cls(rows, "north_band", "seal") == "FIT"                    # a marine band is the sea, cold here


def test_marine_band_takes_its_marine_regions_temperature(synthetic):
    # without it a marine band would have no country; firefox (arid) on a cold sea is three steps
    rows, _ = synthetic[0]()
    assert cls(rows, "north_band", "firefox") == "MISFIT"


def test_one_step_is_a_fit(synthetic):
    # a desert fox on temperate plains is a neighbour, not the wrong country; without it the audit cries wolf
    rows, _ = synthetic[0]()
    assert cls(rows, "lake", "firefox") == "FIT"
    assert cls(rows, "woods", "firefox") == "MISFIT"                   # cool taiga: two steps from arid


def test_waterway_is_judged_in_the_sub_regions_its_polyline_crosses(synthetic):
    # without it a creek would carry no climate; this creek lies in the cool woods, so the arid fox misfits there
    rows, _ = synthetic[0]()
    assert cls(rows, "creek", "firefox", neededNearbyBlocks=["minecraft:water"]) == "MISFIT"


def test_species_with_no_spawn_data_is_judged_by_type_and_says_so(synthetic):
    # without it a species the jar never spawns would be unjudgeable; an ice type in a desert is a misfit
    rows, _ = synthetic[0]()
    r = rows[("dunes", "frostling", "{}")]
    assert r["class"] == "MISFIT" and r["basis"].startswith("type")


def test_modded_only_volcanic_tag_counts_as_arid(synthetic):
    # without it every is_volcanic native (Magmar's kind) would fall to the type rule
    rows, _ = synthetic[0]()
    assert cls(rows, "dunes", "lavaling") == "FIT"
    assert rows[("dunes", "lavaling", "{}")]["basis"] == "jar natives"


def test_cave_only_natives_have_no_country(synthetic):
    # without it a lush-caves species would be judged by type instead of by its own data
    rows, _ = synthetic[0]()
    assert cls(rows, "peak", "caveling") == "FIT"


def test_conditions_that_change_the_country_give_fit_by_condition(synthetic):
    # without it an entry confined underground or to a named biome would be judged as if it spawned everywhere
    rows, _ = synthetic[0]()
    assert cls(rows, "peak", "digger") == "MISFIT"                     # on the cold surface: arid, three steps
    assert cls(rows, "peak", "digger", maxY=40) == "FIT-BY-CONDITION"  # under the place's ground p10 (100), cave-native
    assert cls(rows, "peak", "firefox", biomes=["minecraft:desert"]) == "FIT-BY-CONDITION"


def test_owner_starter_family_is_judged_with_the_row_quoted(synthetic):
    # without it an owner placement would fail the audit; the quote is what lets a reader check the ruling
    rows, _ = synthetic[0]()
    r = rows[("woods", "leafmon2", "{}")]
    assert r["class"] == "JUDGED"                                      # leafmon's evolution, walked through the jar
    assert 'Leafmon: the woods (find)' in r["why"] and r["heart"]


def test_known_ruling_holds_a_misfit_and_a_stale_ruling_is_reported(synthetic):
    # without it a fixed defect's ruling would outlive it, or a ruled defect would fail every prepare
    run = synthetic[0]
    rows, stale = run(known={("strand", "icecrab"): "ruled", ("strand", "crab"): "fits now"})
    assert cls(rows, "strand", "icecrab") == "KNOWN"
    assert stale == [("strand", "crab")]


def test_cli_fails_on_an_unjudged_misfit(synthetic, tmp_path, monkeypatch, capsys):
    # without it prepare would carry on past a wrong-country spawn
    _run, _jar, base = synthetic
    (base / "regions.json").write_text(json.dumps(make_regions()), encoding="utf-8")
    (base / "ww.json").write_text(json.dumps(WATERWAYS), encoding="utf-8")
    (base / "sp.json").write_text(json.dumps(MARINE_SPAWNS), encoding="utf-8")
    (base / "doc.md").write_text(DOC, encoding="utf-8")
    monkeypatch.setattr(A, "owner_starters", lambda doc, jar, families=27: {})
    monkeypatch.setattr(A, "KNOWN", {})
    code = A.main(["--pack", str(base / "pack"), "--jar", str(base / "fake-cobblemon.jar"),
                   "--regions", str(base / "regions.json"), "--waterways", str(base / "ww.json"),
                   "--spawns", str(base / "sp.json"), "--design-doc", str(base / "doc.md"), "--show", "MISFIT"])
    out = capsys.readouterr().out
    assert code == 1 and "unjudged misfit" in out and "icecrab" in out


def test_a_route_entry_naming_no_sub_region_fails_closed(synthetic, tmp_path):
    # without it a corridor entry with an unparseable id would be silently dropped from the sweep
    run, _jar, base = synthetic
    pack = make_pack(base / "pack2", extra={("routes", "r02"): [entry("r02_b0000_nowhere_crab", "crab")]})
    with pytest.raises(A.AuditError, match="names no sub-region"):
        run(pack_dir=pack)


# ------------------------------------------------------------------------------------------- the real data
def _real_jar():
    import battle_sim
    try:
        path = A.find_jar()
    except battle_sim.SimError as ex:
        pytest.skip("no Cobblemon 1.8 jar on this machine: %s" % ex)
    return A.Jar(path)


@pytest.fixture(scope="module")
def real_jar():
    return _real_jar()


def _real_inputs():
    load = lambda p: json.loads((ROOT / p).read_text(encoding="utf-8"))  # noqa: E731
    return (load("data/regions.json"), load("data/waterways.json"), load("data/spawns.json"),
            (ROOT / "docs" / "mechanics" / "ENCOUNTER_DESIGN.md").read_text(encoding="utf-8"))


def _compile(spawns_path, out):
    import compile_spawns
    assert compile_spawns.main(["--spawns", str(spawns_path), "--out", str(out)]) == 0
    return out


@pytest.fixture(scope="module")
def real_rows(real_jar, tmp_path_factory):
    pack = _compile(ROOT / "data" / "spawns.json", tmp_path_factory.mktemp("real") / "cobblers_spawns")
    regions, waterways, spawns, doc = _real_inputs()
    return A.audit(pack, real_jar, regions, waterways, spawns, doc)


def test_the_compiled_pack_has_no_unjudged_misfit_and_no_stale_ruling(real_rows):
    # the owner's sweep itself: without it a wrong-country spawn could reach the server unnoticed
    rows, stale = real_rows
    misfits = ["%s at %s: %s" % (r["species"], r["place_id"], r["why"]) for r in rows if r["class"] == "MISFIT"]
    assert not misfits, misfits
    assert not stale, stale


def test_the_builders_five_fixes_hold_in_the_compiled_pack(real_rows):
    # the 2026-10-04 fixes (commit be0bc12): without it a regenerated table could bring the seven species back
    # Keyed on the FIRST TOKEN of the compiled pokemon string: since 2026-10-05 a heart entry is "<species> alpha=true"
    # (ENCOUNTER_DESIGN.md section 10), and keyed on the whole string a removed species brought back as a heart alpha
    # ("crabominable alpha=true") would not equal "crabominable" and would pass unseen.
    rows, _ = real_rows
    first = lambda s: str(s).split()[0]  # noqa: E731
    present = {(r["place_id"], first(r["species"])) for r in rows}
    for gone in [("south_strand", "crabominable"), ("mt_clay", "sandshrew"), ("mt_clay", "sandslash"),
                 ("the_crags", "crustle"), ("tilpey_waters", "wailord"), ("tilpey_south_shore", "shellos"),
                 ("tilpey_south_shore", "gastrodon")]:
        assert gone not in present, gone
    for kept in [("south_strand", "crabrawler"), ("mt_clay", "rhyhorn"), ("the_crags", "druddigon"),
                 ("tilpey_waters", "basculegion"), ("tilpey_south_shore", "crawdaunt")]:   # tier 7 shows Crawdaunt
        got = {r["class"] for r in rows if (r["place_id"], first(r["species"])) == kept}
        assert got == {"FIT"}, (kept, got)


def test_section_11_names_the_27_owner_starter_families(real_jar):
    # without it a reworded section 11 would silently stop judging the owner's placements
    doc = (ROOT / "docs" / "mechanics" / "ENCOUNTER_DESIGN.md").read_text(encoding="utf-8")
    starters = A.owner_starters(doc, real_jar)
    assert {"piplup", "empoleon", "grookey", "rillaboom", "fennekin", "fuecoco", "skeledirge"} <= set(starters)


def test_mutating_the_generator_brings_crabominable_back_and_the_audit_catches_it(real_jar, tmp_path, monkeypatch):
    # independence: the generator's drop_stages is disabled (data/encounter_design.json untouched), the design is
    # regenerated into a scratch spawns.json and compiled; an audit that shared the builder's derivation would pass
    import build_encounters as BE

    def no_drop(stages, t, tid, used):
        used.update(t.get("drop_stages") or {})         # keep the stale-entry check quiet; drop nothing
        return stages
    monkeypatch.setattr(BE, "drop_stages", no_drop)
    scratch = tmp_path / "spawns.json"
    shutil.copyfile(ROOT / "data" / "spawns.json", scratch)
    assert BE.main(["--spawns", str(scratch), "--jar", str(real_jar.path)]) == 0
    pack = _compile(scratch, tmp_path / "cobblers_spawns")
    regions, waterways, spawns, doc = _real_inputs()
    rows, _ = A.audit(pack, real_jar, regions, waterways, spawns, doc)
    hit = [r for r in rows if str(r["species"]).split()[0] == "crabominable" and r["place_id"] == "south_strand"]
    assert hit and all(r["class"] == "MISFIT" for r in hit), hit


def test_prepare_runs_the_audit_right_after_the_spawns_compile():
    # without it the audit exists and never runs: the owner's "a success report is not the work"
    import reapply
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="x", server_dir="x"))]
    assert names.index("spawn_habitat_audit") == names.index("compile_spawns") + 1
