"""Settlement rules: check_towns and the towns.json schema entry in tools/validate_data.py.

Each rule has a passing baseline and a minimal breaking change. The fixture is a synthetic data
directory in tmp_path (world.json with export.border and no heightmap, progression.json,
towns.json); data/towns.json is only read by the last test, never modified.

Expected values come from the rules as written in data/towns.json "rules" and the task brief
(ten critical towns, off-path distance bands, 600/300 spacing), not from earlier validator output.

Not covered: whether a centre is on land, above water or reachable; whether the recorded
distance_from_critical_path_blocks matches the routed path (the number is trusted as written);
whether role and tier agree with each other (e.g. a gym_town with tier "outpost" is not checked);
waystone kinds and positions; and anything in game (waystones actually unlocking on a flag,
towns existing in the exported world). Those need a terrain run or an in-game experiment.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import validate_data as V  # noqa: E402

BORDER = {"min_x": 0, "min_z": 0, "max_x": 9999, "max_z": 9999}
HALF = 50  # footprint half-width around the centre


# ------------------------------------------------------------------ fixture


def town(tid, role, x, z, **kw):
    critical = role in ("hometown", "gym_town", "league")
    tier = {"major_town": "major", "rest_stop": "rest_stop", "outpost": "outpost"}.get(role, "critical")
    rec = {
        "id": tid,
        "role": role,
        "tier": tier,
        "status": "proposed",
        "critical_path": critical,
        "order": None,
        "centre": {"x": x, "z": z},
        "footprint": {},
        "waystone": {"kind": "flag"} if critical else {"kind": "none"},
    }
    if not critical:
        rec["gates"] = []
    place(rec, x, z)
    rec.update(kw)
    return rec


def place(rec, x, z):
    rec["centre"] = {"x": x, "z": z}
    rec["footprint"] = {"min_x": x - HALF, "max_x": x + HALF, "min_z": z - HALF, "max_z": z + HALF}
    return rec


def baseline_towns():
    """Ten critical towns 1000 blocks apart along z=500, plus one of each off-path role at z=2000."""
    towns = [town("hometown", "hometown", 500, 500, order=0)]
    for i in range(1, 9):
        towns.append(town("gym%d_town" % i, "gym_town", 500 + 1000 * i, 500, order=i))
    towns.append(town("league", "league", 9500, 500, order=9))
    towns.append(town("major_a", "major_town", 500, 2000, distance_from_critical_path_blocks=500))
    towns.append(town("rest_a", "rest_stop", 2000, 2000, distance_from_critical_path_blocks=200))
    towns.append(town("outpost_a", "outpost", 3500, 2000, distance_from_critical_path_blocks=300))
    return towns


def flags_for(towns):
    return [{"id": "%s_cleared" % t["id"], "waystone": {"town": t["id"]}}
            for t in towns if t.get("role") == "gym_town"] + [{"id": "no_waystone_flag"}]


def by_id(towns, tid):
    return next(t for t in towns if t["id"] == tid)


def run(tmp_path, towns, flags=None, world=None):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    if world is None:
        world = {"schema": "cobblers.world/1", "export": {"border": BORDER}}
    (d / "world.json").write_text(json.dumps(world, indent=1), encoding="utf-8")
    (d / "progression.json").write_text(json.dumps(
        {"schema": "cobblers.progression/1", "chapters": [],
         "flags": flags_for(towns) if flags is None else flags}, indent=1), encoding="utf-8")
    (d / "towns.json").write_text(json.dumps({"schema": "cobblers.towns/1", "towns": towns}, indent=1),
                                  encoding="utf-8")
    ctx = V.Context(d, None, V.Report())
    V.check_schema(ctx)
    V.check_towns(ctx)
    return ctx.report.findings


def errors(findings, check="towns"):
    return [f.message for f in findings if f.check == check and f.severity == V.ERROR]


def towns_schema_errors(findings):
    return [f.message for f in findings
            if f.check == "schema" and f.severity == V.ERROR and f.file == "data/towns.json"]


# ----------------------------------------------------------------- baseline


# removing this lets every breaking-change test below pass on a fixture that was already failing
def test_baseline_fixture_has_no_town_or_schema_errors(tmp_path):
    findings = run(tmp_path, baseline_towns())
    assert errors(findings) == []
    assert towns_schema_errors(findings) == []


# removing this lets check_towns fall out of the CLI's CHECKS list unnoticed
def test_cli_runs_the_towns_check(tmp_path, capsys):
    towns = baseline_towns()
    by_id(towns, "rest_a")["gates"] = ["gym3_cleared"]
    run(tmp_path, towns)
    V.main(["--data", str(tmp_path / "data"), "--only", "towns", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert any(f["check"] == "towns" and "gates progression" in f["message"] for f in out["findings"])


# ------------------------------------------------------ critical path counts


# removing this lets the critical path lose its hometown, a gym town or the League
@pytest.mark.parametrize("drop,role,expected", [
    ("hometown", "hometown", 1), ("gym8_town", "gym_town", 8), ("league", "league", 1)])
def test_critical_path_missing_role_is_an_error(tmp_path, drop, role, expected):
    towns = [t for t in baseline_towns() if t["id"] != drop]
    errs = errors(run(tmp_path, towns))
    assert errs == ["the critical path needs %d %s, found %d" % (expected, role, expected - 1)]


# removing this lets a second hometown, a ninth gym town or a second League onto the critical path
@pytest.mark.parametrize("role,expected", [("hometown", 1), ("gym_town", 8), ("league", 1)])
def test_critical_path_extra_role_is_an_error(tmp_path, role, expected):
    towns = baseline_towns()
    towns.append(town("extra", role, 5000, 5000, order=10))
    errs = errors(run(tmp_path, towns))
    assert errs == ["the critical path needs %d %s, found %d" % (expected, role, expected + 1)]


# ------------------------------------------------------------------ orders


# removing this lets a critical town sit on the route without a position in it
def test_critical_town_without_order_is_an_error(tmp_path):
    towns = baseline_towns()
    by_id(towns, "gym4_town")["order"] = None
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and "gym4_town" in errs[0] and "unique order" in errs[0]


# removing this lets two critical towns claim the same place in the route
def test_critical_towns_sharing_an_order_is_an_error(tmp_path):
    towns = baseline_towns()
    by_id(towns, "gym2_town")["order"] = 1
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and "unique order" in errs[0]


# removing this lets an off-path settlement carry a route order (0 guards against a truthiness test)
@pytest.mark.parametrize("order", [0, 3])
def test_off_path_order_must_be_null(tmp_path, order):
    towns = baseline_towns()
    by_id(towns, "major_a")["order"] = order
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and "major_a" in errs[0] and "route order" in errs[0]


# ------------------------------------------------------------ critical_path


# removing this lets critical_path disagree with role in either direction
@pytest.mark.parametrize("tid,value", [
    ("gym5_town", False), ("gym5_town", None), ("hometown", False), ("league", False),
    ("major_a", True), ("rest_a", True), ("outpost_a", True)])
def test_critical_path_flag_must_match_role(tmp_path, tid, value):
    towns = baseline_towns()
    if value is None:
        del by_id(towns, tid)["critical_path"]
    else:
        by_id(towns, tid)["critical_path"] = value
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and tid in errs[0] and "critical_path" in errs[0]


# ------------------------------------------------------------------- gates


# removing this lets an optional settlement gate progression
@pytest.mark.parametrize("tid", ["major_a", "rest_a", "outpost_a"])
def test_off_path_gates_must_be_empty(tmp_path, tid):
    towns = baseline_towns()
    by_id(towns, tid)["gates"] = ["gym3_cleared"]
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and tid in errs[0] and "gates progression" in errs[0]


# removing this makes an off-path record without a gates key an error, although it gates nothing
def test_off_path_without_gates_key_is_fine(tmp_path):
    towns = baseline_towns()
    del by_id(towns, "rest_a")["gates"]
    assert errors(run(tmp_path, towns)) == []


# ------------------------------------------------- distance from the path


# removing this lets rest stops drift outside 100-450 and major towns/outposts crowd the route
@pytest.mark.parametrize("tid,distance,ok", [
    ("rest_a", 100, True), ("rest_a", 450, True), ("rest_a", 99, False), ("rest_a", 451, False),
    ("major_a", 250, True), ("major_a", 5000, True), ("major_a", 249, False),
    ("outpost_a", 250, True), ("outpost_a", 5000, True), ("outpost_a", 249, False)])
def test_distance_from_critical_path_band(tmp_path, tid, distance, ok):
    towns = baseline_towns()
    by_id(towns, tid)["distance_from_critical_path_blocks"] = distance
    errs = errors(run(tmp_path, towns))
    if ok:
        assert errs == []
    else:
        assert len(errs) == 1 and tid in errs[0] and "from the critical path" in errs[0]


# removing this lets an off-path settlement skip recording how far it is from the route
@pytest.mark.parametrize("tid", ["major_a", "rest_a", "outpost_a"])
@pytest.mark.parametrize("how", ["missing", "null"])
def test_distance_from_critical_path_is_required_off_path(tmp_path, tid, how):
    towns = baseline_towns()
    rec = by_id(towns, tid)
    if how == "missing":
        del rec["distance_from_critical_path_blocks"]
    else:
        rec["distance_from_critical_path_blocks"] = None
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and tid in errs[0] and "from the critical path" in errs[0]


# ----------------------------------------------------------------- spacing


# removing this lets two towns (any non-outpost pair) sit closer than 600 blocks
@pytest.mark.parametrize("x,ok", [(1100, True), (1099, False)])
def test_non_outpost_settlements_need_600_blocks(tmp_path, x, ok):
    towns = baseline_towns()
    place(by_id(towns, "rest_a"), x, 2000)  # major_a is at (500, 2000)
    errs = errors(run(tmp_path, towns))
    if ok:
        assert errs == []
    else:
        assert len(errs) == 1 and "major_a" in errs[0] and "rest_a" in errs[0] and "at least 600" in errs[0]


# removing this lets two critical towns crowd each other
def test_critical_towns_need_600_blocks(tmp_path):
    towns = baseline_towns()
    place(by_id(towns, "gym1_town"), 1000, 500)  # hometown is at (500, 500)
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and "at least 600" in errs[0]


# removing this lets an outpost sit on top of a town, or rejects an outpost 300-599 blocks from one
@pytest.mark.parametrize("x,ok", [(2299, False), (2300, True), (2599, True)])
def test_outpost_needs_300_blocks_from_a_town(tmp_path, x, ok):
    towns = baseline_towns()
    place(by_id(towns, "outpost_a"), x, 2000)  # rest_a is at (2000, 2000)
    errs = errors(run(tmp_path, towns))
    if ok:
        assert errs == []
    else:
        assert len(errs) == 1 and "outpost_a" in errs[0] and "at least 300" in errs[0]


# removing this lets an outpost sit closer than 300 to a critical town or to another outpost
# gym3_town is at (3500, 500); outpost_b is added at (3500, 2000), outpost_a moved 299 blocks from `other`
@pytest.mark.parametrize("other,x,z", [("gym3_town", 3500, 799), ("outpost_b", 3500, 2299)])
def test_outpost_needs_300_blocks_from_anything(tmp_path, other, x, z):
    towns = baseline_towns()
    towns.append(town("outpost_b", "outpost", 3500, 2000, distance_from_critical_path_blocks=300))
    place(by_id(towns, "outpost_a"), x, z)
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and other in errs[0] and "at least 300" in errs[0]


# ---------------------------------------------------- centre and footprint


# removing this lets a town's centre fall outside its own footprint (edges are inside)
@pytest.mark.parametrize("dx,dz,ok", [(HALF, 0, True), (0, -HALF, True), (HALF + 1, 0, False), (0, -HALF - 1, False)])
def test_centre_must_lie_inside_footprint(tmp_path, dx, dz, ok):
    towns = baseline_towns()
    rec = by_id(towns, "major_a")
    rec["centre"] = {"x": rec["centre"]["x"] + dx, "z": rec["centre"]["z"] + dz}
    errs = errors(run(tmp_path, towns))
    if ok:
        assert errs == []
    else:
        assert len(errs) == 1 and "major_a" in errs[0] and "outside its footprint" in errs[0]


# removing this lets a footprint cross world.export.border (touching the border edge is inside)
@pytest.mark.parametrize("key,value,ok", [
    ("max_x", 9999, True), ("max_x", 10000, False), ("min_z", 0, True), ("min_z", -1, False),
    ("min_x", -1, False), ("max_z", 10000, False)])
def test_footprint_must_lie_inside_border(tmp_path, key, value, ok):
    towns = baseline_towns()
    rec = by_id(towns, "outpost_a")
    rec["footprint"][key] = value
    errs = errors(run(tmp_path, towns))
    if ok:
        assert errs == []
    else:
        assert len(errs) == 1 and "outpost_a" in errs[0] and "world border" in errs[0]


# removing this lets a record without usable centre/footprint coordinates pass the containment checks
def test_footprint_without_coordinates_is_an_error(tmp_path):
    towns = baseline_towns()
    del by_id(towns, "rest_a")["footprint"]["max_x"]
    errs = errors(run(tmp_path, towns))
    assert len(errs) == 1 and "rest_a" in errs[0] and "footprint min/max" in errs[0]


# removing this lets the border rule pass silently when world.json has no export.border to check against
def test_missing_border_is_reported_not_silently_passed(tmp_path):
    towns = baseline_towns()
    by_id(towns, "outpost_a")["footprint"]["max_x"] = 10 ** 9  # would cross any plausible border
    findings = run(tmp_path, towns, world={"schema": "cobblers.world/1"})
    assert [f for f in findings if f.check == "towns" and f.severity in (V.ERROR, V.SKIPPED)
            and "border" in f.message]


# -------------------------------------------------------------- duplicates


# removing this lets two settlement records share an id
def test_duplicate_town_id_is_an_error(tmp_path):
    towns = baseline_towns()
    dup = copy.deepcopy(by_id(towns, "major_a"))
    place(dup, 5000, 5000)
    towns.append(dup)
    errs = errors(run(tmp_path, towns))
    assert errs == ['duplicate town "major_a"']


# -------------------------------------------------- progression waystones


# removing this lets a progression flag point its waystone at a town that does not exist
def test_flag_naming_unknown_town_is_an_error(tmp_path):
    towns = baseline_towns()
    flags = flags_for(towns) + [{"id": "ghost_flag", "waystone": {"town": "ghost_town"}}]
    errs = errors(run(tmp_path, towns, flags=flags))
    assert len(errs) == 1 and "ghost_flag" in errs[0] and "not in towns.json" in errs[0]


# removing this lets progression tie a waystone to an optional, off-path settlement
@pytest.mark.parametrize("tid", ["major_a", "rest_a", "outpost_a"])
def test_flag_naming_off_path_town_is_an_error(tmp_path, tid):
    towns = baseline_towns()
    flags = flags_for(towns) + [{"id": "bad_flag", "waystone": {"town": tid}}]
    errs = errors(run(tmp_path, towns, flags=flags))
    assert len(errs) == 1 and "bad_flag" in errs[0] and "off-path" in errs[0]


# removing this makes flags naming the hometown or the League errors, although they are on the path
def test_flag_naming_hometown_or_league_is_fine(tmp_path):
    towns = baseline_towns()
    flags = flags_for(towns) + [{"id": "a", "waystone": {"town": "hometown"}},
                                {"id": "b", "waystone": {"town": "league"}}]
    assert errors(run(tmp_path, towns, flags=flags)) == []


# ------------------------------------------------------------------ schema


# removing this lets an unknown role or tier (or one field's value in the other) through the schema
@pytest.mark.parametrize("field,value", [
    ("role", "village"), ("role", "critical"), ("tier", "legendary"), ("tier", "gym_town")])
def test_role_and_tier_enums_reject_unknown_values(tmp_path, field, value):
    towns = baseline_towns()
    by_id(towns, "major_a")[field] = value
    errs = towns_schema_errors(run(tmp_path, towns))
    assert len(errs) == 1 and "major_a" in errs[0] and '%s="%s"' % (field, value) in errs[0]


# removing this lets every accepted role and tier value be rejected by a tightened enum
def test_role_and_tier_enums_accept_every_documented_value():
    _, _, _, enums = V.SCHEMAS["towns.json"]
    assert enums["role"] == {"hometown", "gym_town", "league", "major_town", "rest_stop", "outpost"}
    assert enums["tier"] == {"critical", "major", "rest_stop", "outpost"}


# removing this lets a town record omit (or null) a field the rest of the tooling depends on
@pytest.mark.parametrize("field", ["id", "role", "tier", "status", "centre", "footprint", "waystone"])
@pytest.mark.parametrize("how", ["missing", "null"])
def test_required_town_fields(tmp_path, field, how):
    towns = baseline_towns()
    rec = by_id(towns, "rest_a")
    if how == "missing":
        del rec[field]
    else:
        rec[field] = None
    errs = towns_schema_errors(run(tmp_path, towns))
    assert any('missing required field "%s"' % field in e for e in errs), errs


# removing this lets a towns.json with the wrong schema id be read as towns
def test_towns_schema_id_is_checked(tmp_path):
    run(tmp_path, baseline_towns())
    p = tmp_path / "data" / "towns.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["schema"] = "cobblers.towns/2"
    p.write_text(json.dumps(doc), encoding="utf-8")
    ctx = V.Context(tmp_path / "data", None, V.Report())
    V.check_schema(ctx)
    assert any("cobblers.towns/1" in m for m in towns_schema_errors(ctx.report.findings))


# ------------------------------------------------------------- real data


# removing this lets data/towns.json and data/progression.json break the settlement rules unnoticed
def test_repository_towns_pass_check_towns():
    ctx = V.Context(ROOT / "data", None, V.Report())
    V.check_schema(ctx)
    V.check_towns(ctx)
    assert "towns.json" in ctx.files
    assert errors(ctx.report.findings) == []
    assert towns_schema_errors(ctx.report.findings) == []
