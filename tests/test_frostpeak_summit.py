"""tools/frostpeak_summit.py and its audit tools/frostpeak_summit_audit.py: Frostpeak's summit dressed round
Articuno's tower.

Written by the same agent that wrote the generator and the audit (2026-10-02), disclosed: the repository prefers a
different author for a validator, and both should be re-read by someone else. To keep the audit from sharing the
generator's derivation it imports nothing from the generator (asserted below), takes the tower's box from the
structure catalogue's footprint string rather than the site record's `size`, and takes the camp's viewpoints from
data/frostpeak_camp.json and the heightmap by the seat convention.

Mutations are of the GENERATOR (monkeypatched functions and constants of tools/frostpeak_summit.py), never of the
record: data/frostpeak_summit.json is never edited here. Each mutation must make the named audit check fail.

NOT COVERED: anything in a running server (the integrating session's probes, from `python tools/frostpeak_summit.py
plan`); whether the export's surface on the table is snow (ASSUMED); how the dressing looks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import frostpeak_summit as FS  # noqa: E402
import frostpeak_summit_audit as FA  # noqa: E402

FN_REL = "data/cobblers/function/frostpeak_summit/build.mcfunction"


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is not available here (%s)" % (str(e) or type(e).__name__)[:80])


def built(g, tmp):
    files, p = FS.build(g)
    FS.write(files, tmp)
    return files, p


def failing(rep):
    return {r["check"].split(" ")[0] for r in rep.problems}


@pytest.fixture(scope="module")
def clean(ground, tmp_path_factory):
    out = tmp_path_factory.mktemp("summit") / "pack"
    files, p = built(ground, out)
    return out, files, p


def test_the_audit_imports_nothing_from_the_generator():
    text = (ROOT / "tools" / "frostpeak_summit_audit.py").read_text(encoding="utf-8")
    assert "import frostpeak_summit\n" not in text and "from frostpeak_summit " not in text
    assert "frostpeak_summit as" not in text


def test_the_built_pack_audits_clean(clean, ground):
    out, _files, _p = clean
    rep = FA.audit(out, ground)
    assert not rep.problems, rep.problems


def test_the_build_is_deterministic(clean, ground):
    _out, files, _p = clean
    again, _ = FS.build(ground)
    assert again[FN_REL] == files[FN_REL]


def test_the_dressing_is_sparse_and_keeps_the_table(clean):
    _out, _files, p = clean
    assert 6 <= len(p["tors"]) <= 12
    plants = sum(t["plants"] for t in p["tors"])
    # the summit table to radius 60 is about 1.13 ha: a fellfield, not a meadow
    assert 30 <= plants <= 300, plants
    assert all(t["radius"] >= 40 for t in p["tors"])


def test_the_way_arrives_on_the_ridge_and_leaves_by_the_north_door(clean, ground):
    _out, _files, p = clean
    doc = FS.load()
    line = p["way"]["line"]
    door = doc["tower"]["door"]
    assert door["x"][0] <= line[0][0] <= door["x"][1] and line[0][1] < door["step_z"]
    # the arrival bearing is the one whose ground stays highest 100-200 blocks out, recomputed here
    cx, cz = doc["site"]["centre"]
    import math

    def score(b):
        a = math.radians(b)
        return sum(ground(round(cx + math.sin(a) * r), round(cz - math.cos(a) * r)) for r in range(100, 201, 10))

    assert score(p["way"]["bearing"]) == max(score(b) for b in range(0, 360, 5))


def test_the_step_holds_every_write(clean):
    _out, files, _p = clean
    steps = FS.placement_steps()
    assert steps[2] == ("fn", "cobblers:frostpeak_summit/build")
    x0, z0, x1, z1 = (int(v) for v in steps[0][1].split()[2:])
    blocks, _ = FA.replay(files[FN_REL])
    assert all(x0 <= x <= x1 and z0 <= z <= z1 for x, _y, z in blocks)
    assert steps[3][1] == steps[0][1].replace("add", "remove")


# ------------------------------------------------------------------------------------------------- the audit's harness
def test_harness_the_sight_check_sees_a_block_on_the_line_and_not_one_below_it(ground):
    eyes = FA.viewpoints(ground)
    box = FA.tower_box()
    tgt = FA.targets(box)
    e = np.array(eyes[1])
    t = tgt[len(tgt) // 2]
    mid = e + (t - e) * 0.6
    on = {(int(mid[0]), int(mid[1]), int(mid[2])): "minecraft:stone"}
    assert FA.blocks_on_sight(on, [eyes[1]], tgt)
    below = {(int(mid[0]), int(mid[1]) - 60, int(mid[2])): "minecraft:stone"}
    assert not FA.blocks_on_sight(below, eyes, tgt)


def test_harness_the_viewpoints_are_the_camp_telescope(ground):
    camp = json.loads((ROOT / "data" / "frostpeak_camp.json").read_text(encoding="utf-8"))
    tx, tz = next(p for p in camp["pieces"] if p["id"] == "frostpeak_camp_telescope")["at"]
    eyes = FA.viewpoints(ground)
    assert all(abs(x - (tx + 0.5)) < 1e-9 and abs(z - (tz + 0.5)) < 1e-9 for x, _y, z in eyes)
    assert all(100 < y < 130 for _x, y, _z in eyes)


# ----------------------------------------------------------------------------------- mutations of the generator
def test_mutation_a_tower_box_believed_three_blocks_south_runs_the_way_into_the_tower(ground, tmp_path, monkeypatch):
    real = FS.tower_box

    def shifted(doc=None):
        x0, z0, x1, z1 = real(doc)
        return x0, z0 + 3, x1, z1 + 3

    monkeypatch.setattr(FS, "tower_box", shifted)
    built(ground, tmp_path / "pack")
    assert "S1" in failing(FA.audit(tmp_path / "pack", ground))


def test_mutation_gateposts_pulled_into_the_door_lane(ground, tmp_path, monkeypatch):
    real = FS.cairns

    def inward(doc, line):
        axis = line[0][0]
        return [(k, x + (2 if x < axis else -2) if abs(x - axis) <= 6 else x, z) for k, x, z in real(doc, line)]

    monkeypatch.setattr(FS, "cairns", inward)
    built(ground, tmp_path / "pack")
    assert "S2" in failing(FA.audit(tmp_path / "pack", ground))


def test_mutation_tors_lifted_into_the_camps_line_of_sight(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(FS, "SEAT_LIFT", 20)
    built(ground, tmp_path / "pack")
    assert "S3" in failing(FA.audit(tmp_path / "pack", ground))


def test_mutation_a_flower_that_is_a_spawn_condition(ground, tmp_path, monkeypatch):
    real = FS.pick

    def flowery(table, u):
        v = real(table, u)
        return "minecraft:azure_bluet" if v == "minecraft:fern" else v

    monkeypatch.setattr(FS, "pick", flowery)
    built(ground, tmp_path / "pack")
    rep = FA.audit(tmp_path / "pack", ground)
    assert any(r["check"] == "S4 spawn conditions" for r in rep.problems), rep.problems


def test_mutation_a_lantern_on_the_cairns(ground, tmp_path, monkeypatch):
    real = FS.cairn_blocks

    def lit(doc, kind, x, z, g):
        return [(a, b, c, "minecraft:lantern" if blk == "minecraft:cobblestone_wall" else blk)
                for a, b, c, blk in real(doc, kind, x, z, g)]

    monkeypatch.setattr(FS, "cairn_blocks", lit)
    built(ground, tmp_path / "pack")
    rep = FA.audit(tmp_path / "pack", ground)
    assert any(r["check"] == "S5 light" for r in rep.problems), rep.problems


def test_mutation_rime_on_the_lee_side(ground, tmp_path, monkeypatch):
    real = FS.rime

    def leeward(doc, tor, g):
        ice, share = real(doc, tor, g)
        return {(x + 2 + max(k[0] for k in tor["rock"]) - x, y, z): v for (x, y, z), v in ice.items()}, share

    monkeypatch.setattr(FS, "rime", leeward)
    built(ground, tmp_path / "pack")
    assert "S6" in failing(FA.audit(tmp_path / "pack", ground))


def test_mutation_plants_moved_out_of_the_lee(ground, tmp_path, monkeypatch):
    real = FS.lee

    def windward(doc, tor, g):
        out = real(doc, tor, g)
        west = min(x for x, _y, _z in tor["rock"]) - 12
        return {(west - (x - min(k[0] for k in out)), y, z): v for (x, y, z), v in out.items()}

    monkeypatch.setattr(FS, "lee", windward)
    built(ground, tmp_path / "pack")
    assert "S9" in failing(FA.audit(tmp_path / "pack", ground))
