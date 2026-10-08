"""tools/spawn_tiers_audit.py: every area has a rare table, an ultra-rare table, a heart and enough species.

Written by the test author, not by the sessions building the 2026-10-05 spawn redesign (the owner: "every area should
have a rare, ultra rare, and boss table. need to see a little more variety").

What is asserted: on hand-built packs whose counts can be read off the fixture, the audit passes a pack that meets
every threshold in the tool's header and fails each property alone (rare < 2, ultra-rare < 1, no heart, a heart box
outside the area's base boxes, a heart 128 blocks from a route, a heart in a route, a land or water floor short by one,
a species rare-only in more than half the areas, an unknown area kind); the CLI's exit codes and table. Independence:
the real generator (tools/compile_spawns.py build_subregions) is run on a fixture-sized input and then MUTATED --
the ultra-rare bucket dropped from its source, its heart_boxes emptied, its heart boxes moved, heart_pokemon's alpha
dropped, alpha stamped on the base rows, a heart's locals dropped, a Mega den line laid under heart ids -- with the input
data untouched, and the audit must catch each. The fixture input carries one Mega den (a fixture gulch file) so the den
lines, boxed and non-heart, are exercised. Against the real data (compiled now from data/ into a scratch dir) the audit
must report 0 failures: the redesign landed 2026-10-05 and the former strict xfail was removed.

Not covered (validity is not runtime behaviour): that Cobblemon draws the buckets at their rates in game, that a heart
is felt as a boss, and anything about the habitat pools; those need a running server and an experiment.
"""
from __future__ import annotations

import copy
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import spawn_tiers_audit as A  # noqa: E402


def sp(area, tag, pokemon, bucket="common", pos="grounded", box=(0, 63, 0, 63)):
    return {"id": "%s_%s_%s" % (area, tag, pokemon.replace(" ", "_")), "pokemon": pokemon, "type": "pokemon",
            "spawnablePositionType": pos, "bucket": bucket, "level": "5-10", "weight": 1.0,
            "condition": {"minX": box[0], "maxX": box[1], "minZ": box[2], "maxZ": box[3]}}


def area(name, land=0, water=0, rare=2, ultra=1, heart=True, base_boxes=((0, 63, 0, 63), (64, 127, 0, 63)),
         heart_box=(64, 95, 0, 31)):
    """One area's spawns: `land` grounded and `water` surface species on every base box, `rare` rare and `ultra`
    ultra-rare species (all named after the area, so no species is shared), and a heart on heart_box: a signature
    boss of its own plus one exact local (the area's first base species), both alpha=true (section 10, 2026-10-05)."""
    out = []
    for n, b in enumerate(base_boxes):
        t = "b%04d" % n
        out += [sp(name, t, "%s_land%02d" % (name, i), box=b) for i in range(land)]
        out += [sp(name, t, "%s_fish%02d" % (name, i), pos="surface", box=b) for i in range(water)]
        out += [sp(name, t, "%s_rare%d" % (name, i), "rare", box=b) for i in range(rare)]
        out += [sp(name, t, "%s_ultra%d" % (name, i), "ultra-rare", box=b) for i in range(ultra)]
    if heart:
        out.append(sp(name, "h0000", "%s_boss alpha=true" % name, "uncommon", box=heart_box))
        local = out[0]
        out.append(sp(name, "h0000", "%s alpha=true" % local["pokemon"], "uncommon", local["spawnablePositionType"],
                      box=heart_box))
    return out


def good():
    """Five areas, one of each kind and a water-named sub-region: 12 grounded species on land, exactly 8 water
    species on each water body, rare exactly 2, ultra-rare exactly 1, one heart species inside its base boxes."""
    return {
        ("subregions", "oak_lake"): area("oak_lake", land=12, water=8),
        ("subregions", "elm_woods"): area("elm_woods", land=12),
        ("routes", "route_x"): area("route_x", land=12, heart=False, base_boxes=((1000, 1031, 0, 31),)),
        ("marine", "deep_band"): area("deep_band", water=8, base_boxes=((0, 63, 5000, 5063),),
                                      heart_box=(0, 31, 5000, 5031)),
        ("waterways", "creek_one"): area("creek_one", water=8, base_boxes=((0, 63, 9000, 9063),),
                                         heart_box=(32, 63, 9032, 9063)),
    }


def fails_of(areas):
    return A.audit(areas)[1]


# Without this the fixture could be failing for a reason no test names, and every "fails on X" below proves nothing.
def test_a_pack_meeting_every_threshold_passes():
    rows, failures = A.audit(good())
    assert failures == []
    lake = next(r for r in rows if r["area"] == "subregions/oak_lake")
    # 12 + 8 + 2 + 1 + the heart's boss; the heart's second species is a local, already counted among the 12
    assert (lake["species"], lake["water_species"], lake["rare"], lake["ultra_rare"], lake["heart_species"]) == (24, 8, 2, 1, 2)


# Without this an area with no ultra-rare table passes, the owner's first complaint.
def test_an_area_without_an_ultra_rare_species_fails():
    a = good()
    a[("subregions", "elm_woods")] = area("elm_woods", land=12, ultra=0)
    assert fails_of(a) == ["subregions/elm_woods: ultra-rare table holds 0 species, needs >= 1"]


# Without this a rare "table" of one fixed species passes.
def test_a_rare_table_of_one_species_fails():
    a = good()
    a[("routes", "route_x")] = area("route_x", land=12, rare=1, heart=False, base_boxes=((1000, 1031, 0, 31),))
    assert fails_of(a) == ["routes/route_x: rare table holds 1 species, needs >= 2"]


# Without this a heart's own rare row would stand in for the place's rare table.
def test_a_rare_species_only_in_the_heart_does_not_make_a_rare_table():
    a = good()
    lake = area("oak_lake", land=12, water=8, rare=1)
    lake.append(sp("oak_lake", "h0000", "oak_lake_heartrare alpha=true", "rare", box=(64, 95, 0, 31)))
    a[("subregions", "oak_lake")] = lake
    assert fails_of(a) == ["subregions/oak_lake: rare table holds 1 species, needs >= 2"]


# Without this a place with no boss passes.
@pytest.mark.parametrize("key", [("subregions", "elm_woods"), ("marine", "deep_band"), ("waterways", "creek_one")])
def test_an_area_without_a_heart_fails(key):
    a = good()
    a[key] = [s for s in a[key] if "_h0000_" not in s["id"]]
    assert fails_of(a) == ["%s/%s: no heart (boss) entries" % key]


# Without this a heart compiled into the wrong place (outside its own base table) passes.
def test_a_heart_box_outside_the_areas_base_boxes_fails():
    a = good()
    # (120, 135) pokes 8 blocks past the base boxes' x edge at 127
    a[("subregions", "elm_woods")] = area("elm_woods", land=12, heart_box=(120, 135, 0, 31))
    f = fails_of(a)
    assert len(f) == 1 and f[0].startswith("subregions/elm_woods: 1 of 1 heart boxes outside")


# Without this a heart lying across two base boxes would be judged outside (the union, not one box, is the area).
def test_a_heart_spanning_two_base_boxes_is_inside():
    a = good()
    a[("subregions", "elm_woods")] = area("elm_woods", land=12, heart_box=(32, 95, 0, 63))
    assert fails_of(a) == []


# Without this a heart beside the path passes (section 10: no heart cell within 128 blocks of a route box).
def test_a_heart_128_blocks_from_a_route_fails_and_129_passes():
    a = good()
    # the oak_lake and elm_woods hearts end at x95; a route box starting at x223 is 128 blocks away, x224 is 129
    a[("routes", "route_x")] = area("route_x", land=12, heart=False, base_boxes=((223, 254, 0, 31),))
    f = fails_of(a)
    assert sorted(f) == ["subregions/elm_woods: heart box 128 blocks from a route box, needs > 128",
                         "subregions/oak_lake: heart box 128 blocks from a route box, needs > 128"]
    a[("routes", "route_x")] = area("route_x", land=12, heart=False, base_boxes=((224, 255, 0, 31),))
    assert fails_of(a) == []


# Without this heart content could reach a corridor, which section 10 says it never does.
def test_a_route_carrying_a_heart_fails():
    a = good()
    a[("routes", "route_x")] = area("route_x", land=12, base_boxes=((1000, 1031, 0, 31),), heart_box=(1000, 1031, 0, 31))
    assert fails_of(a) == ["routes/route_x: a route carries 2 heart entries (section 10: never)"]


# Without this a thin land table passes; 11 is one short of section 4's 6 families x 2 stages.
def test_eleven_land_species_fail_and_twelve_pass():
    a = good()
    a[("subregions", "elm_woods")] = area("elm_woods", land=8)  # 8 + 2 rare + 1 ultra = 11, the heart makes 12
    assert fails_of(a) == []
    a[("subregions", "elm_woods")] = area("elm_woods", land=7)
    assert fails_of(a) == ["subregions/elm_woods: 11 species, needs >= 12"]


# Without this a lake with a few fish passes ("a pokemon lake deep in life").
@pytest.mark.parametrize("key", [("subregions", "oak_lake"), ("marine", "deep_band"), ("waterways", "creek_one")])
def test_a_water_body_with_seven_water_species_fails(key):
    a = good()
    a[key] = [s for s in a[key] if not s["pokemon"].endswith("_fish07")]
    assert fails_of(a) == ["%s/%s: 7 water species, needs >= 8 (a water body)" % key]


# Without this the water floor would land on every dry place, or miss a lake named for its water.
def test_only_areas_named_for_water_are_water_bodies():
    assert A.is_water_body("subregions", "shrew_lake_shores")
    assert A.is_water_body("subregions", "tilpey_waters")
    assert A.is_water_body("subregions", "river_of_shrews_vale")
    assert A.is_water_body("marine", "windward_open") and A.is_water_body("waterways", "mt_clay_outflow")
    assert not A.is_water_body("subregions", "elm_woods")
    assert not A.is_water_body("subregions", "lakeside")  # a whole word, not a substring
    assert not A.is_water_body("routes", "route_02_lake")


# Without this a species rare in most places passes, and "rare" stops meaning anything.
def test_a_species_rare_only_in_more_than_half_the_areas_fails():
    a = good()
    for key in [("subregions", "oak_lake"), ("subregions", "elm_woods"), ("routes", "route_x")]:
        a[key].append(sp(key[1], "b0000", "dratini", "rare", box=A.box_of(a[key][0])))
    assert fails_of(a) == ["species dratini: rare-or-ultra-rare only in 3 of 5 areas (more than half)"]
    # common in one of them: rare-only in 2 of 5, under half
    a[("routes", "route_x")].append(sp("route_x", "b0000", "dratini", "common", box=(1000, 1031, 0, 31)))
    assert fails_of(a) == []


# Without this a regional form would count as a new species and pad the floor.
def test_a_form_is_the_same_species():
    assert A.species_of("vulpix alolan") == A.species_of("Vulpix") == "vulpix"


# Without this a new compiled kind (or a misfiled file) is silently ungraded.
def test_an_unknown_area_kind_fails_closed():
    a = good()
    a[("caves", "deep_cave")] = area("deep_cave", land=12)
    assert fails_of(a) == ["caves/deep_cave: unknown area kind 'caves': this audit does not know how to grade it"]


# Without this the coverage test could pass a heart over a gap between two base boxes.
def test_coverage_needs_every_block():
    assert A.covered((0, 9, 0, 9), [(0, 4, 0, 9), (5, 9, 0, 9)])
    assert not A.covered((0, 9, 0, 9), [(0, 4, 0, 9), (6, 9, 0, 9)])
    assert not A.covered((0, 9, 0, 9), [(0, 9, 0, 8)])


# Without this a heart compiled as a plain spawn passes, and the owner's "the boss pokemon are alphas" is lost.
@pytest.mark.parametrize("key", [("subregions", "elm_woods"), ("marine", "deep_band"), ("waterways", "creek_one")])
def test_a_heart_entry_without_alpha_true_fails(key):
    a = good()
    for s in a[key]:
        if "_h0000_" in s["id"] and s["pokemon"].endswith("_boss alpha=true"):
            s["pokemon"] = s["pokemon"].replace(" alpha=true", "")
    f = fails_of(a)
    assert len(f) == 1 and f[0].startswith("%s/%s: 1 heart species not alpha=true" % key), f
    # alpha=false is not an alpha either
    for s in a[key]:
        if s["pokemon"].endswith("_boss"):
            s["pokemon"] += " alpha=false"
    assert len(fails_of(a)) == 1


# Without this an alpha could leak onto a base row, a Mega den line or a corridor, where a boss was never meant to be.
@pytest.mark.parametrize("key", [("subregions", "oak_lake"), ("routes", "route_x"), ("waterways", "creek_one")])
def test_an_alpha_outside_a_heart_fails(key):
    a = good()
    a[key][0]["pokemon"] += " alpha=true"
    f = fails_of(a)
    # the local the heart named was the area's first base species; it is no longer an exact match, so only the
    # alpha failure is asked for here, and the local one is allowed alongside it
    assert any(x.startswith("%s/%s: 1 non-heart species carry an alpha key" % key) for x in f), f
    assert all(x.startswith("%s/%s: " % key) for x in f), f


# Without this a heart made only of outsiders passes ("it should sometimes be the pokemon in the area as well").
@pytest.mark.parametrize("key", [("subregions", "elm_woods"), ("marine", "deep_band"), ("waterways", "creek_one")])
def test_a_heart_without_an_exact_local_fails(key):
    a = good()
    a[key] = [s for s in a[key] if not ("_h0000_" in s["id"] and not s["pokemon"].endswith("_boss alpha=true"))]
    assert fails_of(a) == ["%s/%s: heart holds no exact local (none of its species is in the area's own non-heart "
                           "entries; section 10: every heart holds one of its own place's Pokemon)" % key]


# Without this a regional form would pass as its plain species' local (the Alolan Vulpix is not the meadow's Vulpix).
def test_a_different_form_is_not_an_exact_local():
    a = good()
    for s in a[("subregions", "elm_woods")]:
        if "_h0000_" in s["id"] and not s["pokemon"].endswith("_boss alpha=true"):
            s["pokemon"] = s["pokemon"].replace(" alpha=true", " alolan alpha=true")
    assert len(fails_of(a)) == 1 and "heart holds no exact local" in fails_of(a)[0]
    assert A.without_alpha("Vulpix alolan alpha=true") == "vulpix alolan" and A.without_alpha("ditto is_alpha") == "ditto"


def write_pack(root, areas):
    for (kind, name), spawns in areas.items():
        f = root / "data" / "cobblers" / "spawn_pool_world" / kind / ("%s.json" % name)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"enabled": True, "spawns": spawns}), encoding="utf-8")


# Without this the prepare job could exit 0 on a failing pack, or on no pack at all.
def test_cli_exit_codes_and_table(tmp_path, capsys):
    out = tmp_path / "out"
    assert A.main(["--pack", str(tmp_path / "none"), "--out", str(out)]) == 2
    write_pack(tmp_path / "ok", good())
    assert A.main(["--pack", str(tmp_path / "ok"), "--out", str(out)]) == 0
    rows = (out / "areas.tsv").read_text(encoding="utf-8").splitlines()
    assert rows[0].split("\t") == list(A.COLUMNS) and len(rows) == 6
    bad = good()
    bad[("subregions", "elm_woods")] = area("elm_woods", land=12, ultra=0, heart=False)
    write_pack(tmp_path / "bad", bad)
    capsys.readouterr()
    assert A.main(["--pack", str(tmp_path / "bad"), "--out", str(out)]) == 1
    printed = capsys.readouterr().out.splitlines()
    assert printed[0].startswith("spawn_tiers_audit: 5 areas, 1 failing, 2 failures")
    assert printed[1:] == ["FAIL subregions/elm_woods: ultra-rare table holds 0 species, needs >= 1; no heart (boss) entries"]
    assert len((out / "failures.txt").read_text(encoding="utf-8").splitlines()) == 2


@pytest.fixture(scope="module")
def real_pack(tmp_path_factory):
    """The pack compiled now from data/ (tools/compile_spawns.py main, unmutated) into a scratch dir: build/ is
    disposable and absent from a fresh checkout, and a stale one would grade yesterday's data."""
    import compile_spawns
    out = tmp_path_factory.mktemp("tiers_real") / "cobblers_spawns"
    assert compile_spawns.main(["--out", str(out)]) == 0
    return out


# The real data: the redesign landed (rows A-D, E-H, alphas; 2026-10-05), so every area meets every check. Without it a
# regenerated table could drop an area's ultra-rare, its heart, its alphas or its local, and prepare would install it.
def test_the_real_compiled_pack_meets_every_tier(real_pack):
    areas = A.load(real_pack)
    kinds = [k for k, _ in areas]
    # ENCOUNTER_DESIGN.md section 1 counts 63 sub-region tables; the marine bands and the waterway carry hearts too
    assert kinds.count("subregions") == 63 and "marine" in kinds and "waterways" in kinds, sorted(set(kinds))
    assert A.audit(areas)[1] == []


# Without this the audit exists and never runs (the owner's "a success report is not the work").
def test_prepare_runs_the_audit_after_the_compile_and_the_habitat_audit():
    import reapply
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="x", server_dir="x"))]
    assert names.index("spawn_tiers_audit") == names.index("spawn_habitat_audit") + 1
    assert names.index("spawn_habitat_audit") == names.index("compile_spawns") + 1


# ---- independence: the generator, mutated, on a fixture-sized input; the input data never changes ----

FAR = -200000  # far from every spawn-free zone in data/spawn_suppression.json, which the generator reads


def gen_input():
    """Two sub-regions, each: 10 common, 2 rare, 1 ultra-rare; a heart (alpha, as data/encounter_design.json
    rules.hearts.alpha makes every generated heart entry) holding a signature boss and one local, land00. The
    sub-region records carry the level_band the Mega den lines read (tools/compile_spawns.py mega_den_spawns)."""
    def square(x0):
        return [[[x0, FAR], [x0 + 256, FAR], [x0 + 256, FAR + 256], [x0, FAR + 256]]]

    subs = [{"id": "gen_meadow", "polygons": square(FAR)}, {"id": "gen_grove", "polygons": square(FAR + 1024)}]
    entries = []
    for s in subs:
        x0 = s["polygons"][0][0][0]
        heart = {"kind": "focus", "x": x0 + 128, "z": FAR + 128, "radius": 48}

        def e(species, bucket, **extra):
            return dict({"mechanism": "spawn_json_coordinate_boxes", "ambient": True, "weight": 1.0,
                         "scope": s["id"], "species": species, "bucket": bucket, "level": "5-10"}, **extra)

        entries += [e("%s_land%02d" % (s["id"], i), "common") for i in range(10)]
        entries += [e("%s_rare%d" % (s["id"], i), "rare") for i in range(2)]
        entries.append(e("%s_ultra" % s["id"], "ultra-rare"))
        entries.append(e("%s_boss" % s["id"], "uncommon", heart=heart, alpha=True))
        entries.append(e("%s_land00" % s["id"], "uncommon", heart=heart, alpha=True))
    spawn_subs = [{"id": s["id"], "level_band": {"minimum": 5, "maximum": 10}} for s in subs]
    return {"entries": entries, "subregions": spawn_subs}, {"routes": []}, {"subregions": subs}


# One Mega field den in gen_meadow (the data/gulch_mine.json shape mega_den_spawns reads): its line compiles as boxed,
# natural, non-heart spawns inside the area -- the case the old condition split misread as a heart.
GULCH_FIXTURE = {"mega_field": {"families": {"box_half": 25, "band": 2, "family_weight": 2.0, "bucket": "common",
                                             "held": {}, "lines": {"denmon": ["denmon", "denmon2"]}}},
                 "farms": [{"dens": [{"id": "gm_fixture_den", "species": "denmon", "anchor": [FAR + 64, 70, FAR + 64]}]}]}


@pytest.fixture
def gulch(tmp_path):
    f = tmp_path / "gulch_fixture.json"
    f.write_text(json.dumps(GULCH_FIXTURE), encoding="utf-8")
    return f


def compiled(cs, gulch):
    """The generator's sub-region half on gen_input(), reading the fixture gulch instead of the real one (whose den
    anchors lie in no fixture sub-region, and which the generator then rightly refuses)."""
    spawns, routes, regions = gen_input()
    real = cs.GULCH
    cs.GULCH = gulch
    try:
        files, _ = cs.build_subregions(spawns, routes, regions, 32, ())
    finally:
        cs.GULCH = real
    return {("subregions", Path(rel).stem): json.loads(text)["spawns"] for rel, text in files.items()}


def mutated_compile_spawns(old, new):
    """compile_spawns loaded from its own source with one exact edit; fails if the anchor is gone or not unique."""
    src = (ROOT / "tools" / "compile_spawns.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, "mutation anchor moved: %r" % old
    mod = types.ModuleType("compile_spawns_mutant")
    mod.__file__ = str(ROOT / "tools" / "compile_spawns.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


# Without this the audit could agree with the generator by construction; the unmutated generator must pass, Mega den
# line and alpha hearts included.
def test_the_unmutated_generator_passes_on_the_fixture_input(gulch):
    import compile_spawns
    areas = compiled(compile_spawns, gulch)
    assert len(areas) == 2 and fails_of(areas) == []
    den = [s for s in areas[("subregions", "gen_meadow")] if "_gm_fixture_den_" in s["id"]]
    hearts = [s for s in areas[("subregions", "gen_meadow")] if "_h0000_" in s["id"]]
    assert {s["pokemon"] for s in den} == {"denmon", "denmon2"}, "the fixture den laid nothing; it exercises nothing"
    assert {s["pokemon"] for s in hearts} == {"gen_meadow_boss alpha=true", "gen_meadow_land00 alpha=true"}


# Without this a generator that silently drops the ultra-rare bucket would pass the audit.
def test_a_generator_dropping_the_ultra_rare_bucket_is_caught(gulch):
    cs = mutated_compile_spawns("        for e in base:\n",
                                "        for e in [q for q in base if q[\"bucket\"] != \"ultra-rare\"]:\n")
    assert sorted(fails_of(compiled(cs, gulch))) == [
        "subregions/gen_grove: ultra-rare table holds 0 species, needs >= 1",
        "subregions/gen_meadow: ultra-rare table holds 0 species, needs >= 1"]


# Without this a generator that stops laying hearts would pass the audit.
def test_a_generator_dropping_hearts_is_caught(monkeypatch, gulch):
    import compile_spawns
    monkeypatch.setattr(compile_spawns, "heart_boxes", lambda *a, **k: [])
    assert sorted(fails_of(compiled(compile_spawns, gulch))) == ["subregions/gen_grove: no heart (boss) entries",
                                                          "subregions/gen_meadow: no heart (boss) entries"]


# Without this a generator laying a heart outside its place would pass the audit.
def test_a_generator_moving_hearts_out_of_their_area_is_caught(monkeypatch, gulch):
    import compile_spawns
    real = compile_spawns.heart_boxes
    monkeypatch.setattr(compile_spawns, "heart_boxes",
                        lambda *a, **k: [(b[0] + 4096, b[1] + 4096, b[2], b[3]) for b in real(*a, **k)])
    f = fails_of(compiled(compile_spawns, gulch))
    assert len(f) == 2 and all("heart boxes outside the area's base boxes" in x for x in f)


# Without this a generator that stops writing alpha=true (heart_pokemon) would ship the bosses as ordinary spawns.
def test_a_generator_dropping_the_alpha_flag_is_caught(gulch):
    cs = mutated_compile_spawns(
        '    return entry["species"] + (" alpha=true" if entry.get("alpha") is True else "")\n',
        '    return entry["species"]\n')
    f = sorted(fails_of(compiled(cs, gulch)))
    assert [x.split(" (")[0] for x in f] == ["subregions/gen_grove: 2 heart species not alpha=true",
                                            "subregions/gen_meadow: 2 heart species not alpha=true"], f


# Without this a generator stamping alpha on the base roster would make every spawn a boss and pass.
def test_a_generator_putting_alpha_on_base_rows_is_caught(gulch):
    cs = mutated_compile_spawns('% (sub["id"], n, e["species"].replace(" ", "_")), "pokemon": e["species"],',
                                '% (sub["id"], n, e["species"].replace(" ", "_")), "pokemon": heart_pokemon(dict(e, alpha=True)),')
    f = sorted(fails_of(compiled(cs, gulch)))
    # the base land00 now reads "land00 alpha=true", so the heart's local no longer matches a plain base row either
    assert [x.split(" (")[0] for x in f] == ["subregions/gen_grove: 13 non-heart species carry an alpha key",
                                            "subregions/gen_grove: heart holds no exact local",
                                            "subregions/gen_meadow: 13 non-heart species carry an alpha key",
                                            "subregions/gen_meadow: heart holds no exact local"], f


# Without this a generator that lays only the outsiders of a heart (its locals dropped) would pass the audit.
def test_a_generator_dropping_the_hearts_locals_is_caught(gulch):
    anchor = '        hboxes = heart_boxes(sub, hearts[0]["heart"], grid, exclude, waterways)\n'
    cs = mutated_compile_spawns(anchor, anchor + '        hearts = [q for q in hearts if q["species"] not in {x["species"] for x in base}]\n')
    f = sorted(fails_of(compiled(cs, gulch)))
    assert [x.split(" (")[0] for x in f] == ["subregions/gen_grove: heart holds no exact local",
                                            "subregions/gen_meadow: heart holds no exact local"], f


# Without this the Mega den lines, laid under heart ids, would read as a boss table; the alpha check names them.
def test_a_generator_laying_den_lines_as_hearts_is_caught(gulch):
    cs = mutated_compile_spawns('rows.append({"id": "%s_%s_b%d_%s" % (sub, d["id"], bi, sp),',
                                'rows.append({"id": "%s_h%04d_%s" % (sub, 9000 + bi, sp),')
    f = fails_of(compiled(cs, gulch))
    assert [x.split(" (")[0] for x in f] == ["subregions/gen_meadow: 2 heart species not alpha=true"], f
