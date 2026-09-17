"""check_foliage in tools/validate_data.py: data/foliage.json against regions, the object library, paint tables,
world bounds and the landmark-tree outposts in towns.json.

Each rule has a passing baseline and a minimal breaking change. The fixture is a synthetic repository in tmp_path:
data/{world,regions,towns,foliage}.json and kits/structures/foliage/ with real .nbt files written by
tools/structure_nbt.py and hashed. Plant sets, terrain codes and biomes come from the real tools/paint_maps.py.
The last test runs the check on the real data/ and kits/ (read only).

Not covered: whether the forest types look right, whether placement honours them (tests/test_foliage_place.py),
whether library objects measure correctly (tests/test_foliage_objects.py), and anything in game.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import structure_nbt as S  # noqa: E402
import validate_data as V  # noqa: E402

SITE = [500, 600]


def _foliage():
    return {
        "schema": "cobblers.foliage/1",
        "density_model": {"noise": {"ragged_scale": 96, "glade_scale": 320, "clump_scale": 72},
                          "water_clearance_blocks": 3, "settlement_clearance_blocks": 16},
        "types": {
            "woods": {
                "identity": "Test woods.", "from_inside": "Trees.", "stems_per_ha": 100, "edge_width": 40,
                "ragged": 10, "glade_share": 0.1, "clumping": 0.2, "slope_lo": 18, "slope_hi": 32,
                "biome": "minecraft:taiga",
                "classes": [{"group": "spruce", "core": 1, "edge": 2, "spacing": 5}],
                "lone": {"per_ha": 1, "reach": 80, "groups": ["spruce"]},
                "debris": [{"group": "boulder", "per_ha": 2, "zone": "any", "max_slope": 20, "vertical_offset": -1}],
                "floor": {"threshold": 0.4, "mix": [["PODZOL", 0.6], ["MOSS", 0.4]]},
                "understory": {"core": {"set": "fern_floor", "coverage": 0.1, "clear": True}},
            },
            "hills": {
                "identity": "Test hills.", "from_inside": "Sorted trees.", "stems_per_ha": 50,
                "elevation_sort": {"radius": 128, "span": 24},
                "classes": [{"group": "spruce", "low": 1, "high": 0, "spacing": 5},
                            {"group": "boulder", "low": 0, "high": 1, "spacing": 3}],
            },
            "meadow": {"identity": "Open.", "from_inside": "Grass.", "stems_per_ha": 2, "open": True,
                       "classes": [{"group": "spruce", "core": 1, "edge": 1, "spacing": 8}]},
        },
        "preset_defaults": {"forest": "woods", "plains": "meadow"},
        "assign": {"north_hills": {"type": "hills", "density_scale": 0.8, "why": "test"}},
        "landmark_trees": [{"id": "giant_oak", "object": "landmark_giant", "site": list(SITE), "kind": "route",
                            "glade_radius": 24,
                            "seen_from": [{"kind": "legs", "legs": ["home->gym1"], "spacing": 48},
                                          {"kind": "ring", "radius": 60, "n": 12},
                                          {"kind": "points", "points": [[400, 400]]}],
                            "for": "a test"}],
    }


def _towns():
    def t(tid, role, tier, x, z, order=None, **kw):
        rec = {"id": tid, "role": role, "tier": tier, "order": order, "centre": {"x": x, "z": z},
               "footprint": {"min_x": x - 10, "max_x": x + 10, "min_z": z - 10, "max_z": z + 10}}
        rec.update(kw)
        return rec
    return {"schema": "cobblers.towns/1", "towns": [
        t("home", "hometown", "critical", 100, 100, order=0),
        t("gym1", "gym_town", "critical", 900, 100, order=1),
        t("gym2", "gym_town", "critical", 900, 900, order=2),
        t("giant_oak", "outpost", "outpost", SITE[0], SITE[1], kind="landmark_tree"),
    ]}


def _objects():
    out = {}
    for name, group, blocks in (("spruce_01", "spruce", [(0, y, 0, "minecraft:spruce_log") for y in range(5)]),
                                ("boulder_01", "boulder", [(0, 0, 0, "minecraft:stone"), (1, 0, 0, "minecraft:stone")]),
                                ("landmark_giant", "landmark_giant", [(0, y, 0, "minecraft:oak_log") for y in range(9)])):
        b = S.Builder()
        for x, y, z, n in blocks:
            b.set(x, y, z, n)
        out[name] = (group, b.to_bytes()[0])
    return out


def build(tmp_path, foliage=None, towns=None, regions=None, world=None, skip=()):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    files = {
        "world.json": world if world is not None else {"schema": "cobblers.world/1",
                                                       "bounds": {"min_x": 0, "min_z": 0, "max_x": 999, "max_z": 999}},
        "regions.json": regions if regions is not None else {
            "schema": "cobblers.regions/3", "paint_presets": {"forest": {}, "plains": {}},
            "subregions": [{"id": "north_hills"}, {"id": "south_plain"}]},
        "towns.json": towns if towns is not None else _towns(),
        "foliage.json": foliage if foliage is not None else _foliage(),
    }
    for name, doc in files.items():
        if name not in skip:
            (d / name).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    lib = tmp_path / "kits" / "structures" / "foliage"
    if "library" not in skip:
        lib.mkdir(parents=True, exist_ok=True)
        rows = []
        for name, (group, data) in _objects().items():
            (lib / (name + ".nbt")).write_bytes(data)
            rows.append({"name": name, "file": name + ".nbt", "group": group, "source": "generated",
                         "origin": [0, 0, 0], "sha256": hashlib.sha256(data).hexdigest(), "ground_radius": 0})
        (lib / "library.json").write_text(json.dumps({"schema": "cobblers.foliage_library/1", "objects": rows},
                                                     indent=1), encoding="utf-8")
    return d, lib


def run(d):
    ctx = V.Context(d, None, V.Report())
    V.check_schema(ctx)
    V.check_foliage(ctx)
    return ctx.report.findings


def of(findings, severity):
    return [f.message for f in findings if f.check == "foliage" and f.severity == severity]


def errors_for(tmp_path, mutate=None, **kw):
    foliage = _foliage()
    towns = _towns()
    if mutate:
        mutate(foliage, towns)
    d, _ = build(tmp_path, foliage=foliage, towns=towns, **kw)
    return of(run(d), V.ERROR)


# ------------------------------------------------------------------ baseline and registration

# removing this lets every breaking-change test below pass on a fixture that was already failing
def test_baseline_fixture_is_clean(tmp_path):
    d, _ = build(tmp_path)
    findings = run(d)
    assert of(findings, V.ERROR) == [] and of(findings, V.WARNING) == [] and of(findings, V.SKIPPED) == []
    assert of(findings, V.INFO) == ["checked 3 forest types, 2 object groups, 3 library objects and 1 landmark trees"]


# removing this lets check_foliage fall out of the CLI's CHECKS list unnoticed
def test_cli_runs_the_foliage_check(tmp_path, capsys):
    foliage = _foliage()
    foliage["types"]["woods"]["classes"][0]["group"] = "no_such_group"
    d, _ = build(tmp_path, foliage=foliage)
    assert "foliage" in [name for name, _ in V.CHECKS]
    assert V.main(["--data", str(d), "--only", "foliage", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert any(f["check"] == "foliage" and "no_such_group" in f["message"] for f in out["findings"])


# removing this lets the real foliage data, library and towns drift apart without the validator noticing
def test_real_foliage_data_passes():
    ctx = V.Context(ROOT / "data", None, V.Report())
    V.check_schema(ctx)
    V.check_foliage(ctx)
    bad = [f.message for f in ctx.report.findings if f.check == "foliage" and f.severity in (V.ERROR, V.SKIPPED)]
    assert bad == []


# ------------------------------------------------------------------ absent and malformed files

# removing this lets a missing data/foliage.json pass silently instead of being reported as not checked
def test_absent_foliage_is_skipped_with_a_reason(tmp_path):
    d, _ = build(tmp_path, skip=("foliage.json",))
    findings = run(d)
    assert of(findings, V.ERROR) == []
    assert len(of(findings, V.SKIPPED)) == 1 and "data/foliage.json is absent" in of(findings, V.SKIPPED)[0]


# removing this lets a missing library, regions or towns file quietly disable part of the check
@pytest.mark.parametrize("skip,needle", [
    ("library", "library.json is absent"),
    ("regions.json", "data/regions.json is absent"),
    ("towns.json", "data/towns.json is absent"),
    ("world.json", "no bounds"),
])
def test_absent_dependency_is_skipped_not_passed(tmp_path, skip, needle):
    d, _ = build(tmp_path, skip=(skip,))
    skipped = of(run(d), V.SKIPPED)
    assert len(skipped) == 1 and needle in skipped[0], skipped


# removing this lets a missing tools/paint_maps.py disable plant-set, terrain and biome checks without a trace
def test_absent_paint_tables_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "PAINT_MAPS", tmp_path / "nope" / "paint_maps.py")
    foliage = _foliage()
    foliage["types"]["woods"]["understory"]["core"]["set"] = "not_a_set"
    d, _ = build(tmp_path, foliage=foliage)
    findings = run(d)
    assert of(findings, V.ERROR) == []
    assert any("plant sets" in m for m in of(findings, V.SKIPPED))


# removing this lets a corrupt foliage.json or library.json be skipped (fail open) instead of failing
@pytest.mark.parametrize("target", ["foliage", "library"])
def test_malformed_json_is_an_error(tmp_path, target):
    d, lib = build(tmp_path)
    (d / "foliage.json" if target == "foliage" else lib / "library.json").write_text("{nope", encoding="utf-8")
    errs = of(run(d), V.ERROR)
    assert any("invalid JSON" in m for m in errs), errs


# ------------------------------------------------------------------ schema fields

# removing this lets a type, class, debris or density_model field that placement reads be missing or out of range
@pytest.mark.parametrize("mutate,needle", [
    (lambda f, t: f.update(schema="cobblers.foliage/0"), 'expected "cobblers.foliage/1"'),
    (lambda f, t: f["density_model"]["noise"].pop("glade_scale"), "noise.glade_scale"),
    (lambda f, t: f["density_model"].pop("settlement_clearance_blocks"), "settlement_clearance_blocks"),
    (lambda f, t: f["types"]["woods"].pop("identity"), "identity must be a non-empty string"),
    (lambda f, t: f["types"]["woods"].update(stems_per_ha="many"), "stems_per_ha"),
    (lambda f, t: f["types"]["woods"].update(glade_share=1.5), "glade_share must be between 0 and 1"),
    (lambda f, t: f["types"]["woods"].update(slope_lo=40), "slope_lo 40 is above slope_hi 32"),
    (lambda f, t: f["types"]["woods"].update(classes=[]), "classes must be a non-empty list"),
    (lambda f, t: f["types"]["woods"]["classes"][0].update(spacing=0), "spacing must be a positive number"),
    (lambda f, t: f["types"]["woods"]["classes"][0].update(low=1), "low/high weights need the type's elevation_sort"),
    (lambda f, t: f["types"]["hills"]["classes"][0].update(core=1), "core/edge weights are ignored"),
    (lambda f, t: [c.pop(k) for c in f["types"]["hills"]["classes"] for k in ("low", "high")],
     "needs low/high weights"),
    (lambda f, t: f["types"]["woods"]["debris"][0].update(zone="edge"), "zone 'edge' is not one of any, core"),
    (lambda f, t: f["types"]["woods"]["debris"][0].update(vertical_offset=0.5), "vertical_offset must be an integer"),
    (lambda f, t: f["types"]["woods"]["lone"].update(reach=0), "lone.reach must be a positive number"),
    (lambda f, t: f["types"]["woods"]["understory"].update(canopy={"set": "fern_floor", "coverage": 0.1}),
     "understory zone canopy"),
    (lambda f, t: f["types"]["woods"].update(water_boost={"factor": 2}), "water_boost needs a positive factor and reach"),
    (lambda f, t: f["landmark_trees"][0].update(glade_radius=0), "glade_radius must be a positive number"),
    (lambda f, t: f["landmark_trees"][0].update(site=[500.5, 600]), "site must be [x, z] integers"),
    (lambda f, t: f["landmark_trees"][0]["seen_from"].append({"kind": "sky"}), "seen_from kind 'sky'"),
    (lambda f, t: f["landmark_trees"].append(copy.deepcopy(f["landmark_trees"][0])), 'duplicate landmark tree'),
])
def test_schema_field_breaks_are_errors(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# removing this lets lone trees be configured on an open type, where placement never draws them
def test_lone_trees_on_open_type_warn(tmp_path):
    foliage = _foliage()
    foliage["types"]["meadow"]["lone"] = {"per_ha": 1, "reach": 40, "groups": ["spruce"]}
    d, _ = build(tmp_path, foliage=foliage)
    findings = run(d)
    assert of(findings, V.ERROR) == []
    assert any("never placed for an open type" in m for m in of(findings, V.WARNING))


# ------------------------------------------------------------------ references

# removing this lets a forest type be assigned by a preset or sub-region name that does not exist, or name a type
# that is not defined (paint_maps would raise mid-paint, or the forest would silently not appear)
@pytest.mark.parametrize("mutate,needle", [
    (lambda f, t: f["preset_defaults"].update(forrest="woods"), 'preset_defaults key "forrest" is not a paint preset'),
    (lambda f, t: f["assign"].update(nowhere={"type": "woods"}), 'assign key "nowhere" is not a sub-region'),
    (lambda f, t: f["preset_defaults"].update(plains="prairie"), 'names type "prairie", which is not defined'),
    (lambda f, t: f["assign"]["north_hills"].update(type="mountains"), 'names type "mountains", which is not defined'),
])
def test_unknown_presets_subregions_and_types_are_errors(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# removing this lets a class, lone, debris group or landmark object point at objects the library does not have
# (paint_maps exits mid-paint on the first missing group)
@pytest.mark.parametrize("mutate,needle", [
    (lambda f, t: f["types"]["woods"]["classes"][0].update(group="fir"), 'object group "fir"'),
    (lambda f, t: f["types"]["woods"]["lone"].update(groups=["lone_fir"]), 'object group "lone_fir"'),
    (lambda f, t: f["types"]["woods"]["debris"][0].update(group="log"), 'object group "log"'),
    (lambda f, t: f["landmark_trees"][0].update(object="landmark_missing"), 'object "landmark_missing" must be both'),
    (lambda f, t: f["landmark_trees"][0].update(object="spruce_01"), 'object "spruce_01" must be both'),
])
def test_groups_and_landmark_objects_must_exist_in_library(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# removing this lets a library row describe a file that changed or is gone, so offsets and sizes are stale
@pytest.mark.parametrize("how,needle", [("edit", "sha256 is"), ("delete", "is missing"), ("path", "bare file name")])
def test_library_rows_must_match_their_files(tmp_path, how, needle):
    d, lib = build(tmp_path)
    doc = json.loads((lib / "library.json").read_text(encoding="utf-8"))
    if how == "edit":
        (lib / "boulder_01.nbt").write_bytes((lib / "boulder_01.nbt").read_bytes() + b"\x00")
    elif how == "delete":
        (lib / "boulder_01.nbt").unlink()
    else:
        next(r for r in doc["objects"] if r["name"] == "boulder_01")["file"] = "../boulder_01.nbt"
        (lib / "library.json").write_text(json.dumps(doc), encoding="utf-8")
    errs = of(run(d), V.ERROR)
    assert any("boulder_01" in m and needle in m for m in errs), errs


# removing this lets an understory plant set, floor terrain or biome name that paint_maps cannot paint through
@pytest.mark.parametrize("mutate,needle", [
    (lambda f, t: f["types"]["woods"]["understory"]["core"].update(set="ferns"), "plant set ferns is not in"),
    (lambda f, t: f["types"]["woods"]["floor"]["mix"][0].__setitem__(0, "DIRT"), "floor terrain DIRT is not in"),
    (lambda f, t: f["types"]["woods"]["floor"]["mix"][0].__setitem__(1, 0.5), "shares sum to 0.9, not 1"),
    (lambda f, t: f["types"]["woods"].update(biome="minecraft:spruce_forest"), "biome minecraft:spruce_forest is not in"),
])
def test_paint_table_names_must_exist(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# removing this lets a landmark tree be sited off the map, where placement skips it
def test_landmark_site_outside_bounds_is_an_error(tmp_path):
    def mutate(f, t):
        f["landmark_trees"][0]["site"] = [1200, 600]
        t["towns"][-1]["centre"] = {"x": 1200, "z": 600}
    errs = errors_for(tmp_path, mutate)
    assert errs == ['landmark tree "giant_oak" site (1200, 600) is outside the world bounds']


# removing this lets landmark trees and their outposts in data/towns.json fall out of step (a tree nobody can find
# in the settlement plan, or an outpost with no tree)
@pytest.mark.parametrize("mutate,needle", [
    (lambda f, t: t["towns"].pop(), 'landmark tree "giant_oak" has no outpost'),
    (lambda f, t: t["towns"][-1].update(kind="ruin"), "must be role outpost with kind landmark_tree"),
    (lambda f, t: t["towns"][-1].update(role="rest_stop"), "must be role outpost with kind landmark_tree"),
    (lambda f, t: t["towns"][-1].update(centre={"x": 510, "z": 600}), "is not its outpost centre (510, 600)"),
    (lambda f, t: t["towns"].append(dict(copy.deepcopy(t["towns"][-1]), id="lonely_pine")),
     '"lonely_pine" is a landmark_tree outpost with no entry'),
    (lambda f, t: f["landmark_trees"][0]["seen_from"][0].update(legs=["home->gym2"]),
     'leg "home->gym2", which is not a pair of consecutive critical towns'),
])
def test_landmark_trees_pair_with_outposts(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    assert any(needle in m for m in errs), errs


# removing this lets a demoted giant keep making viewpoint claims, lose its reason, or stay listed as a place
@pytest.mark.parametrize("mutate,needle", [
    (lambda f, t: (f["landmark_trees"][0].update(landmark=False, demoted={"why": "test"}), t["towns"].pop()), None),
    (lambda f, t: (f["landmark_trees"][0].update(landmark=False, demoted={"why": "test"}), t["towns"].pop(),
                   f["landmark_trees"][0].pop("seen_from")), None),
    (lambda f, t: (f["landmark_trees"][0].update(landmark=False, demoted={"why": "test"}),
                   f["landmark_trees"][0].pop("seen_from")), "must not be a place in data/towns.json"),
    (lambda f, t: (f["landmark_trees"][0].update(landmark=False), f["landmark_trees"][0].pop("seen_from"), t["towns"].pop()),
     "needs a demoted record with a why"),
])
def test_demoted_trees(tmp_path, mutate, needle):
    errs = errors_for(tmp_path, mutate)
    if needle is None:
        # the first case still has seen_from, which a demoted tree may not claim; the second is the clean demotion
        assert errs in ([], ['landmark_trees.giant_oak has landmark false, so it makes no seen_from claim']), errs
    else:
        assert any(needle in m for m in errs), errs


# removing this lets a library row without ground_radius through: placement then treats the object as one column
# (group_stats defaults to 0), so a fallen log or boulder lands on unchecked ground
@pytest.mark.parametrize("value", ["missing", -1, 1.5, True, None])
def test_library_rows_need_ground_radius(tmp_path, value):
    d, lib = build(tmp_path)
    doc = json.loads((lib / "library.json").read_text(encoding="utf-8"))
    row = next(r for r in doc["objects"] if r["name"] == "boulder_01")
    if value == "missing":
        row.pop("ground_radius")
    else:
        row["ground_radius"] = value
    (lib / "library.json").write_text(json.dumps(doc), encoding="utf-8")
    errs = of(run(d), V.ERROR)
    assert len(errs) == 1 and "boulder_01" in errs[0] and "ground_radius" in errs[0], errs
