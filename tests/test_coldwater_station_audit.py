"""tools/coldwater_station_audit.py: its primitives on synthetic fixtures with hand-computed values, and its
independence from the builder proved by MUTATING THE GENERATOR (tools/coldwater_station.py) with
data/coldwater_station.json untouched.

Not covered here (validity is not behavior, .claude/rules/testing.md): whether the server accepts the commands, the
NPCs stand once spawned, the displays render along the computed direction, the click advancement fires, the ferry
charges and gates. Those are the in-game probes in data/coldwater_station.json audit_checklist. The sea-pack check
needs build/datapacks/cobblers_sea_life and cobblers_sea_floor, which only a full checkout's prepare builds; here it
is tested on a synthetic function file.
"""
from __future__ import annotations

import ast
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import coldwater_station_audit as A  # noqa: E402

AUDIT_SRC = ROOT / "tools" / "coldwater_station_audit.py"


# ------------------------------------------------------------------------------------------- independence by import
def test_audit_imports_none_of_the_builders():
    # Removing this lets the audit share the builder's derivation (seat, aim, arch geometry) and agree with its bugs.
    tree = ast.parse(AUDIT_SRC.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"coldwater_station", "portals", "frostpeak_camp", "town_dressing", "southern_residents"}


# ------------------------------------------------------------------------------------------------- primitives
def test_bearing_is_clockwise_from_north():
    # Without it a sign could say 270 for a buoy due east and the audit would agree with any convention.
    assert A.bearing(0, -1) == pytest.approx(0)
    assert A.bearing(1, 0) == pytest.approx(90)
    assert A.bearing(0, 1) == pytest.approx(180)
    assert A.bearing(-1, 0) == pytest.approx(270)


def test_quaternion_rotation_turns_z_east_for_a_quarter_turn_about_y():
    # Without it the instrument direction check could pass a display pointing anywhere.
    s = math.sqrt(0.5)
    assert A.qrot([0, s, 0, s], [0, 0, 1]) == pytest.approx([1, 0, 0], abs=1e-9)
    assert A.qrot([0, 0, 0, 1], [0.3, -2, 5]) == pytest.approx([0.3, -2, 5])


def test_segment_distance_hand_values():
    # Without it the lane check (arch inside the ferry lane) measures the wrong thing.
    assert A.seg_dist((5, 3), (0, 0), (10, 0)) == pytest.approx(3)
    assert A.seg_dist((13, 4), (0, 0), (10, 0)) == pytest.approx(5)      # past the end: to the endpoint
    assert A.box_dist(13, 4, (0, 0, 10, 0)) == pytest.approx(5)
    assert A.box_dist(5, 0, (0, 0, 10, 0)) == 0


def test_forceload_check_names_a_write_outside_every_forceload():
    # Without it a write into an unloaded chunk (silently dropped by the server) passes.
    ok = [(1, "forceload add 0 0 15 15"), (2, "setblock 3 64 3 minecraft:stone"), (3, "forceload remove 0 0 15 15")]
    assert A.forceload_problems("t", ok) == []
    bad = [(1, "forceload add 0 0 15 15"), (2, "setblock 40 64 40 minecraft:stone"), (3, "forceload remove 0 0 15 15")]
    assert any("outside every forceload" in p for p in A.forceload_problems("t", bad))
    leak = [(1, "forceload add 0 0 15 15"), (2, "setblock 3 64 3 minecraft:stone")]
    assert any("not the ones removed" in p for p in A.forceload_problems("t", leak))


def test_sea_pack_writes_are_read_through_execute_prefixes(tmp_path):
    # Without it a sea pack writing behind `execute ... run` would never be seen near the arch.
    f = tmp_path / "a.mcfunction"
    f.write_text("# c\nexecute if block 1 2 3 minecraft:water run setblock 1 2 3 minecraft:kelp\n"
                 "fill 9 5 7 4 1 2 minecraft:seagrass replace minecraft:water\n", encoding="utf-8")
    assert list(A.Audit.writes_boxes(f)) == [(1, 2, 3, 1, 2, 3, "minecraft:kelp"),
                                             (4, 1, 2, 9, 5, 7, "minecraft:seagrass")]


def test_authored_sweep_finds_points_boxes_polygons_and_honours_exclusions(tmp_path):
    # Without it the 48-block clearance would see nothing, or would see the station's own jetty record.
    d = tmp_path / "data"
    d.mkdir()
    (d / "a.json").write_text(json.dumps({"things": [
        {"id": "mine", "at": [100, 200]},
        {"id": "excluded", "at": [5, 5], "inner": {"x": 7, "z": 8}},
        {"id": "b", "rect": [0, 0, 10, 10], "polygon": [[0, 0], [4, 0], [4, 4]]},
        {"id": "c", "bounds": {"min_x": 1, "min_z": 2, "max_x": 3, "max_z": 4}}]}), encoding="utf-8")
    (d / "regions.json").write_text(json.dumps({"r": {"polygons": [[[0, 0], [9, 0], [9, 9]]]}}), encoding="utf-8")
    (d / "coldwater_station.json").write_text(json.dumps({"at": [1, 1]}), encoding="utf-8")
    pts, boxes, polys = A.authored_things(tmp_path, {"excluded"})
    assert sorted((x, z) for _s, x, z in pts) == sorted([(100, 200), (0, 0), (4, 0), (4, 4)])
    assert sorted(b for _s, b in boxes) == [(0, 0, 10, 10), (1, 2, 3, 4)]
    assert [p for _s, p in polys] == [[[0, 0], [4, 0], [4, 4]]]
    assert A.in_polygon(3, 1, [[0, 0], [4, 0], [4, 4]]) and not A.in_polygon(1, 3, [[0, 0], [4, 0], [4, 4]])


class _Inputs:
    """The few fields arch_expected and floors_check read, synthetic."""

    def __init__(self, facing="west"):
        self.sea = 62
        self.portals = {"blocks": {"dive": {"apron": "AP", "frame": "FR", "sheet": "SH", "lamp": "LA"}}}
        self.doc = {"portal": {"site": {"at": [100, 200], "facing": facing},
                               "buoy": {"float": "FL", "light": "LI"}},
                    "blocks": {"foundation": "minecraft:cobblestone"},
                    "pieces": [{"id": "p", "at": [0, 0]}]}


def _arch_audit(facing, ground):
    a = A.Audit.__new__(A.Audit)
    a.I = _Inputs(facing)
    a.d = a.I.doc
    a.g = ground
    a.apron_y = max(ground(100 + i, 200 + k) for i in range(-2, 3) for k in range(-2, 3))
    return a


def test_arch_expectation_hand_built_for_west_and_north():
    # Without it the arch geometry check compares the build against an expectation nobody verified.
    ground = lambda x, z: 48 if (x, z) == (98, 198) else 50   # noqa: E731  one corner two low: one footing
    w = _arch_audit("west", ground).arch_expected()
    assert len(w) == 25 + 1 + 15 + 5 + 2
    assert w[(98, 49, 198)] == "AP" and w[(98, 50, 198)] == "AP"          # footing, then the apron at max ground
    assert w[(100, 51, 198)] == "FR" and w[(100, 53, 202)] == "FR"        # jambs at r = -2, +2 (along z)
    assert w[(100, 52, 200)] == "SH" and w[(100, 54, 200)] == "FR"        # sheet, lintel
    assert w[(100, 54, 198)] == "LA" and w[(100, 54, 202)] == "LA"        # lamps
    assert w[(100, 62, 200)] == "FL" and w[(100, 63, 200)] == "LI"        # buoy float at sea level, lantern on it
    n = _arch_audit("north", lambda x, z: 50).arch_expected()
    assert n[(98, 51, 200)] == "FR" and n[(101, 52, 200)] == "SH"         # facing north: the arch runs along x


def _floor_audit(ground, sets):
    a = A.Audit.__new__(A.Audit)
    a.I = _Inputs()
    a.d = a.I.doc
    a.g = ground
    a.results, a.notes = [], []
    a.floors_check(sets)
    return dict(a.results)["station_floors"]


def test_floor_is_max_ground_plus_one_with_foundation_from_ground_plus_one():
    # Without it a piece seated a block high (or buried) passes: the +1 floor mutation would go unseen.
    ground = lambda x, z: 10 if x == 0 else 8   # noqa: E731  floor = 11
    good = [(0, 11, 0, "minecraft:spruce_planks"), (1, 9, 0, "minecraft:cobblestone"),
            (1, 10, 0, "minecraft:cobblestone"), (1, 11, 0, "minecraft:spruce_planks")]
    assert _floor_audit(ground, good) == []
    high = [(0, 11, 0, "minecraft:cobblestone"), (0, 12, 0, "minecraft:spruce_planks"),
            (1, 9, 0, "minecraft:cobblestone"), (1, 10, 0, "minecraft:cobblestone"),
            (1, 11, 0, "minecraft:cobblestone"), (1, 12, 0, "minecraft:spruce_planks")]
    assert any("lowest non-foundation block is at y12" in p for p in _floor_audit(ground, high))
    gap = [(0, 11, 0, "minecraft:spruce_planks"), (1, 10, 0, "minecraft:cobblestone"),
           (1, 11, 0, "minecraft:spruce_planks")]
    assert any("missing y[9]" in p for p in _floor_audit(ground, gap))


# ------------------------------------------------------------------------- the real build and generator mutations
@pytest.fixture(scope="module")
def ground():
    import ground as G
    try:
        return G.load()
    except Exception as e:      # the canonical heightmap is outside the repo
        pytest.skip("canonical heightmap unavailable: %s" % e)


def _build_and_audit(out, ground, argv_extra=()):
    import coldwater_station as CS
    CS.main(["build", "--out", str(out)] + list(argv_extra))
    a = A.Audit(A.Inputs(), out, ground).run()
    return {name: probs for name, probs in a.results}


def test_built_pack_passes_every_check(tmp_path, ground):
    # Without it the mutations below could all "fail" against an audit that fails everything.
    res = _build_and_audit(tmp_path / "pack", ground)
    assert len(res) == 20
    assert {k: v for k, v in res.items() if v} == {}


def test_mutation_arch_moved_out_of_the_lane_fails(tmp_path, ground, monkeypatch):
    # Without it the generator could emit the arch where sea_life grows kelp through it, data untouched.
    import coldwater_station as CS
    orig = CS.arch_functions

    def moved(doc, a):
        a = dict(a)
        a["blocks"] = [(x, y, z - 60, s) for x, y, z, s in a["blocks"]]
        a["click"] = (a["click"][0], a["click"][1], a["click"][2] - 60)
        return orig(doc, a)
    monkeypatch.setattr(CS, "arch_functions", moved)
    res = _build_and_audit(tmp_path / "pack", ground)
    assert res["lane"] and res["arch_geometry"] and res["arch_click"]


def test_mutation_teleport_in_the_stub_fails(tmp_path, ground, monkeypatch):
    # Without it the sealed arch could start moving players before the Kyogre cave exists.
    import coldwater_station as CS
    orig = CS.arch_functions

    def leaky(doc, a):
        fns, adv = orig(doc, a)
        fns["portal/destination"] = fns["portal/destination"] + ["tp @s 0 200 0"]
        return fns, adv
    monkeypatch.setattr(CS, "arch_functions", leaky)
    res = _build_and_audit(tmp_path / "pack", ground)
    assert any("not a stub" in p for p in res["arch_click"])


def test_mutation_telescope_aimed_off_the_buoy_fails(tmp_path, ground, monkeypatch):
    # Without it the telescope could point 4 blocks off the buoy and the board still read as right.
    import coldwater_station as CS
    orig = CS.arch

    def off(doc, g):
        a = orig(doc, g)
        a["lantern"] = [a["lantern"][0], a["lantern"][1], a["lantern"][2] + 4]
        return a
    monkeypatch.setattr(CS, "arch", off)
    res = _build_and_audit(tmp_path / "pack", ground)
    assert any("coldwater_station_telescope" in p for p in res["instruments"])


def test_mutation_researcher_seated_in_a_wall_fails(tmp_path, ground, monkeypatch):
    # Without it a researcher could spawn inside the lab's wall.
    import coldwater_station as CS
    orig = CS.plan

    def walled(doc, g):
        p = orig(doc, g)
        for n in p["npcs"]:
            if n["id"] == "coldwater_station_rask":
                n["at"] = [6042, n["at"][1], 1846]          # the lab's west wall (centre 6045, width 7)
        return p
    monkeypatch.setattr(CS, "plan", walled)
    res = _build_and_audit(tmp_path / "pack", ground)
    assert any("coldwater_station_rask" in p for p in res["npcs"])


def test_mutation_floor_one_high_fails(tmp_path, ground, monkeypatch):
    # Without it every piece could float a block over its ground (or the NPCs with it) unseen.
    import coldwater_station as CS
    orig = CS.FC.seat

    def high(spec, piece, g):
        world, gr, floor = orig(spec, piece, g)
        return world, gr, floor + 1
    monkeypatch.setattr(CS.FC, "seat", high)
    res = _build_and_audit(tmp_path / "pack", ground)
    assert res["station_floors"] and res["npcs"]


def test_mutation_stale_fare_fails(tmp_path, ground, monkeypatch):
    # Without it the board and the researchers could quote a fare the ferry does not charge.
    import coldwater_station as CS
    orig = CS.fill
    monkeypatch.setattr(CS, "fill", lambda text, numbers: orig(text, dict(numbers, fare="300")))
    res = _build_and_audit(tmp_path / "pack", ground)
    assert res["signs"] and res["dialogue"]


def test_reapply_runs_the_audit_after_the_station_and_sea_packs_are_built():
    # Without it prepare never runs the audit, or runs it before the packs it replays exist.
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    audit = text.index('add("coldwater_station_audit"')
    assert audit > text.index('add("coldwater_station:build"')
    assert audit > text.index('add("sea_life:build"') and audit > text.index('add("sea_floor:build"')
