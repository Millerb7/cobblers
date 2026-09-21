"""Commands that do nothing and say nothing are found before they run, and towns are checked by their result.

Each case here happened on the disposable world on 2026-09-21:
  - the town prep functions force-loaded nothing, so their cuts and paving took effect only where chunks were
    still loaded from the step before, and Brock's streets were laid a block off their plan;
  - the town Centres and Marts named templates no installed pack held, so they were never placed;
  - Misty's houses were underwater houses, and their water ran across her streets.
The static rule lives in tools/function_limits.py, the result check in tools/town_audit.py plan_audit().

Written by the same session that wrote those tools; not independently reviewed (docs/HANDOVER_CODEX.md).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits as FL  # noqa: E402
import place_town as PT  # noqa: E402
import structure_nbt as SN  # noqa: E402
import town_audit as TA  # noqa: E402


# ------------------------------------------------------------------ unloaded writes

def test_a_write_into_a_chunk_nobody_loaded_is_flagged():
    assert FL.unloaded_writes(["fill 0 60 0 3 60 3 minecraft:stone"])
    assert FL.check_lines(["setblock 100 60 100 minecraft:stone"])


def test_a_write_after_forceload_passes_and_one_after_release_does_not():
    ok = ["forceload add 0 0 31 31", "fill 0 60 0 31 60 31 minecraft:stone"]
    assert FL.unloaded_writes(ok) == []
    late = ok + ["forceload remove 0 0 31 31", "setblock 5 60 5 minecraft:stone"]
    assert [n for n, _, _ in FL.unloaded_writes(late)] == [4]


def test_execute_run_writes_count_and_relative_ones_do_not():
    assert FL.unloaded_writes(["execute if block 1 2 3 minecraft:jigsaw run setblock 1 2 3 minecraft:air"])
    assert FL.unloaded_writes(["setblock ~ ~ ~ minecraft:air"]) == []


def test_a_function_whose_caller_holds_the_chunks_says_so():
    assert FL.unloaded_writes(["# chunks-loaded-by: cobblers:towns/x", "setblock 0 60 0 minecraft:stone"]) == []


def test_ensure_loaded_holds_every_written_chunk_for_the_whole_run():
    lines = ["# header", "forceload add 0 0 15 15", "setblock 1 60 1 minecraft:stone", "forceload remove 0 0 15 15",
             "fill 40 60 0 70 60 3 minecraft:stone", "place template cobblers:x 200 60 200 none none 1.0 0"]
    out = FL.ensure_loaded(lines)
    assert FL.check_lines(out) == []
    assert out[0] == "# header" and out[1].startswith("# chunks:")
    adds = [l for l in out if l.startswith("forceload add")]
    removes = [l for l in out if l.startswith("forceload remove")]
    assert [l.split(" ", 2)[2] for l in adds] == [l.split(" ", 2)[2] for l in removes]
    assert out[-len(removes):] == removes and not any(l.startswith("forceload") for l in out[2 + len(adds):-len(removes)])
    # a template is held with room round its origin, not just the origin's chunk
    assert (200 - FL.TEMPLATE_REACH) // 16 in {int(a.split()[2]) // 16 for a in adds}


def test_ensure_loaded_leaves_a_sound_function_alone():
    ok = ["forceload add 0 0 15 15", "setblock 1 60 1 minecraft:stone", "forceload remove 0 0 15 15"]
    assert FL.ensure_loaded(ok) == ok


def test_every_forceload_ensure_loaded_writes_stays_under_the_chunk_limit():
    out = FL.ensure_loaded(["fill 0 60 0 %d 60 0 minecraft:stone" % (16 * 300)])
    assert FL.check_lines(out) == []


# ------------------------------------------------------------------ dried templates

OCEAN = [q for q in json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
         if q.get("dry") and q.get("file") and (ROOT / q["file"]).is_file()]


def test_a_dried_copy_holds_no_water_and_keeps_its_shape(tmp_path):
    import nbt
    if not OCEAN:
        import pytest
        pytest.skip("the ocean-village templates are local only (gitignored donor kit)")
    q = OCEAN[0]
    dest = tmp_path / "dry.nbt"
    PT.rewrite_template(ROOT / q["file"], dest, dry=True)
    _, before = nbt.load(ROOT / q["file"])
    _, after = nbt.load(dest)
    names = [p["Name"] for p in after["palette"]]
    assert "minecraft:water" not in names and "minecraft:seagrass" not in names
    assert not any((p.get("Properties") or {}).get("waterlogged") == "true" for p in after["palette"])
    assert len(after["blocks"]) == len(before["blocks"]) and after["size"] == before["size"]
    assert PT.template_info(dest)["entrance_pos"] == PT.template_info(ROOT / q["file"])["entrance_pos"]


# ------------------------------------------------------------------ plan against world

PLAN = {"streets": {"main": {"surface": "minecraft:stone_bricks", "cells": [[0, 64, 0, 9], [1, 64, 0, 9]]}},
        "plaza": {"rect": [20, 0, 23, 3], "y": 65, "surface": "minecraft:polished_andesite"},
        "lamps": [{"street": "main", "at": [5, 65, 0]}], "lamp_block": "minecraft:sea_lantern"}


def fake_world(monkeypatch, tmp_path, blocks):
    b = SN.Builder()
    for (x, y, z), name in blocks.items():
        b.set(x, y, z, name)
    monkeypatch.setattr(SN, "capture", lambda world, lo, hi: b)
    monkeypatch.setattr(TA, "ROOT", tmp_path)
    (tmp_path / "derived" / "towns").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "derived" / "towns" / "t_plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
    (tmp_path / "data" / "placements.json").write_text(json.dumps({"placements": [], "settlements": {}}), encoding="utf-8")
    (tmp_path / "data" / "spawn_block_policy.json").write_text(json.dumps({"substitutions": []}), encoding="utf-8")


def as_built():
    w = {(x, 64, z): "minecraft:stone_bricks" for x in range(10) for z in (0, 1)}
    w.update({(x, 65, z): "minecraft:polished_andesite" for x in range(20, 24) for z in range(4)})
    w[(5, 64, 0)] = "minecraft:sea_lantern"
    return w


def test_a_town_built_as_planned_is_clean(monkeypatch, tmp_path):
    fake_world(monkeypatch, tmp_path, as_built())
    res = TA.plan_audit("t", "world")
    assert res["problems"] == [] and res["lamps"]["lit"] == 1


def test_off_level_paving_a_dark_lamp_and_a_block_on_the_road_are_all_found(monkeypatch, tmp_path):
    w = as_built()
    del w[(3, 64, 1)]
    w[(3, 65, 1)] = "minecraft:stone_bricks"       # laid a block high, as Brock's streets were
    w[(5, 64, 0)] = "minecraft:stone_bricks"       # the lamp never placed
    w[(21, 66, 2)] = "minecraft:cobblestone"       # something standing on the plaza
    fake_world(monkeypatch, tmp_path, w)
    probs = " | ".join(TA.plan_audit("t", "world")["problems"])
    assert "main: 1 of 19 cells not paved as planned (1 a block off level" in probs
    assert "lamps: 1 of 1 spots are not lit" in probs
    assert "plaza: 1 cells have a block standing on the road (cobblestone 1)" in probs


def test_water_standing_on_a_road_is_found(monkeypatch, tmp_path):
    w = as_built()
    w[(2, 65, 0)] = "minecraft:water"
    fake_world(monkeypatch, tmp_path, w)
    assert any("water 1" in p for p in TA.plan_audit("t", "world")["problems"])
