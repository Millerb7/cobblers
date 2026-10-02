"""tools/rift_heightmap.py `plan_target()`: which file `--plan` is allowed to describe.

`--plan` is the only way to rebuild `derived/rift_sculpt/`, and every Rift block pass (rift_skin, gulch_mine,
the audits) reads that folder. Its whole value is the proof it makes before it writes: the sculpt it computes
from `data/rift_sculpt.json` must be, pixel for pixel, a real file that `data/world.json` names AND hashes.

Pointing that proof at the wrong file breaks it in both directions. It used to compare against the heightmap
PIN, which was the sculpt's own output only while the sculpt was the last pass over the heightmap; the water
export (2026-09-29) layered a pass on top, the pin moved to `..._rift_water.png`, and `--plan` then refused in
every checkout -- so the folder became unrebuildable. The opposite failure is quieter and worse: the old code
would have written the PINNED sha into the plan under the label `heightmap: <sculpt output>`, a record that
names one file and hashes another.

These tests drive `plan_target()` directly with synthetic provenance dicts and a few bytes in tmp_path. They do
NOT run `--plan`: that sculpts the whole 8192x8192 heightmap and, at this commit, fails for a real reason
(10,867 columns of drift from a normals fix applied after the sculpt). What is checked here is which file the
proof is aimed at and that the aim is verified -- not that the sculpt reproduces anything.

Two tests mutate `plan_target`'s own source in memory (`_mutant`) rather than the authored record, because a
record-side mutation moves the expectation and the output together and would pass a check that does nothing.
"""
import hashlib
import inspect
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_heightmap as RH  # noqa: E402

OUT = RH.OUT_NAME
PIN_NAME = "land_8k_16_rescaled_b145_pads_rift_water.png"
PIN_SHA = "a" * 64


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _hm(pin_name=PIN_NAME, pin_sha=PIN_SHA, **entries):
    """A synthetic heightmap provenance block: the pin, plus whatever `<x>_from` entries a test needs."""
    hm = {"path": pin_name, "width": 8192, "height": 8192, "sha256": pin_sha, "status": "ok"}
    hm.update(entries)
    return hm


def _chain(tmp_path, body=b"the sculpt's own bytes", pin_body=b"a later pass over the heightmap"):
    """A tmp directory shaped like the source root: the pinned file and the sculpt output beside it."""
    (tmp_path / PIN_NAME).write_bytes(pin_body)
    (tmp_path / OUT).write_bytes(body)
    return tmp_path / PIN_NAME, tmp_path / OUT


def _mutant(*subs):
    """`plan_target` with its own source rewritten, to prove a check bites. The DATA is never relaxed."""
    src = inspect.getsource(RH.plan_target)
    for old, new in subs:
        assert old in src, "mutation target %r is no longer in plan_target's source; re-aim the mutation" % old
        src = src.replace(old, new, 1)
    ns = dict(RH.__dict__)
    exec(compile(src, "<mutant plan_target>", "exec"), ns)  # noqa: S102 - deliberate, in-memory, test-only
    return ns["plan_target"]


# ---------------------------------------------------------------- the pin is the sculpt output


def test_the_pinned_heightmap_is_the_target_when_it_is_the_sculpt_output(tmp_path):
    # Without this, a checkout where the sculpt IS the last pass would verify a redundant hop, and a stale
    # provenance sha (or a missing file beside the heightmap) could override the pin it was meant to describe.
    stale = {"path": OUT, "sha256": "b" * 64, "generator": "an older record of the same name"}
    hm = _hm(pin_name=OUT, water_shaped_from=stale)
    current = tmp_path / OUT          # deliberately NOT written: a walk would have to read it and would fail
    target, sha, via = RH.plan_target(hm, current)
    assert target == current
    assert sha == hm["sha256"] != stale["sha256"]
    assert via == "", "the pin needs no explanation; a note here means a hop was taken"


# ---------------------------------------------------------------- the pin has moved on


def test_a_moved_pin_resolves_through_the_entry_that_names_the_sculpt_output(tmp_path):
    # Without this, --plan compares the computed sculpt against whatever the newest pass left pinned and refuses
    # in every checkout, which is exactly how derived/rift_sculpt/ became unrebuildable on 2026-09-29.
    pin, out = _chain(tmp_path)
    hm = _hm(water_shaped_from={"path": OUT, "sha256": _sha(out), "generator": "python tools/water_shape.py"})
    target, sha, via = RH.plan_target(hm, pin)
    assert target == out
    assert "water_shaped_from" in via and pin.name in via, via


def test_the_sha_the_plan_records_is_the_sculpt_outputs_own_not_the_pinned_one(tmp_path):
    """Without this, the plan says `heightmap: <sculpt output>` beside the sha of a DIFFERENT file.

    That mislabel is what the old code did, and the mutation below restores its net effect -- the pin's sha
    handed back under the sculpt output's name -- so the assertion is shown to distinguish the two. The
    expectation is computed here from the file's own bytes, not read out of the provenance record, so the
    record and the code cannot agree with each other and both be wrong.
    """
    pin, out = _chain(tmp_path)
    recorded = _sha(out)
    hm = _hm(water_shaped_from={"path": OUT, "sha256": recorded})

    _, sha, _ = RH.plan_target(hm, pin)
    assert sha == recorded == _sha(out)
    assert sha != hm["sha256"], "the plan would describe the sculpt output with the pinned file's sha"

    legacy = _mutant(('return target, sha, ", reached', 'return target, hm["sha256"], ", reached'))
    assert legacy(hm, pin)[1] == hm["sha256"], "the mutation did not reproduce the old mislabel"


def test_the_plan_labels_the_sculpt_output_and_records_that_same_files_sha(tmp_path, monkeypatch):
    # Without this, label and value can drift apart again one call site away from plan_target: the plan's
    # `heightmap` key and its `sha256` key must describe one file, since every block pass trusts the pair.
    pin, out = _chain(tmp_path)
    hm = _hm(water_shaped_from={"path": OUT, "sha256": _sha(out)})
    _, sha, _ = RH.plan_target(hm, pin)

    monkeypatch.setattr(RH, "PLAN", tmp_path / "plan" / "plan.json")
    monkeypatch.setattr(RH, "MASK", tmp_path / "plan")
    b = {
        "box": [0, 4, 0, 4], "ring": [(0, 0), (0, 1)], "nrm": [(1.0, 0.0), (0.0, 1.0)],
        "segs": [(0.0, 1.0, "sheer")], "peaks": [], "ent": [(0, {"id": "e", "why": "dropped"}, None)],
        "top": [1.0], "width": [2.0], "floor": [3.0], "plateau": [4.0],
        "changed": np.zeros((2, 2), bool), "basin": np.zeros((2, 2), bool), "footprints": [],
    }
    RH.write_plan(b, sha, 0)
    doc = json.loads(RH.PLAN.read_text(encoding="utf-8"))
    assert doc["heightmap"] == OUT
    assert doc["sha256"] == _sha(tmp_path / OUT), "the plan's sha is not the sha of the file it names"


# ---------------------------------------------------------------- the aim is verified, not assumed


def test_a_sculpt_output_that_does_not_hash_to_the_recorded_sha_is_a_fault(tmp_path):
    """Without this, a file that merely has the right NAME beside the heightmap is accepted as the sculpt.

    A fault, not a warning: `plan_target` raises and returns nothing, so no plan is written. The mutation
    disables only the comparison, and the mutant then accepts the wrong bytes -- which is what proves the real
    check is the thing doing the work, rather than the name match above it.
    """
    pin, out = _chain(tmp_path, body=b"not the sculpt the chain recorded")
    hm = _hm(water_shaped_from={"path": OUT, "sha256": "c" * 64})
    with pytest.raises(RH.SculptError) as e:
        RH.plan_target(hm, pin)
    m = str(e.value)
    assert OUT in m and "water_shaped_from" in m, m
    assert _sha(out)[:12] in m and "cccccccccccc" in m, "the fault names neither the bytes found nor the bytes recorded"

    blind = _mutant(("if got != sha:", "if False:"))
    assert blind(hm, pin)[0] == out, "the mutation did not reach the sha comparison"


def test_a_missing_sculpt_output_names_the_entry_that_promised_it(tmp_path):
    # Without this, the failure is a bare FileNotFoundError from PIL deep inside plan_only, and nothing says
    # which provenance entry claimed the file or that --apply is what puts it back.
    (tmp_path / PIN_NAME).write_bytes(b"only the newest pass survives here")
    hm = _hm(water_shaped_from={"path": OUT, "sha256": "d" * 64})
    with pytest.raises(RH.SculptError) as e:
        RH.plan_target(hm, tmp_path / PIN_NAME)
    m = str(e.value)
    assert "water_shaped_from" in m and OUT in m, m
    assert "--apply" in m, "the fault does not say how to get the sculpt output back"


def test_no_entry_naming_the_sculpt_output_is_a_fault_rather_than_a_guess(tmp_path):
    """Without this, a chain that has forgotten the sculpt would be verified against the nearest plausible
    file -- the pin, or whichever entry sorted first -- and `--plan` would write a plan for a heightmap the
    sculpt never produced. That is worse than no plan at all, because every block pass reads it as fact.
    """
    pin, out = _chain(tmp_path)
    hm = _hm(water_shaped_from={"path": "land_8k_16_rescaled_b145_pads.png", "sha256": "e" * 64},
             rescaled_from={"path": "land_8k_16_sculpted_relief.png", "sha256": "f" * 64})
    with pytest.raises(RH.SculptError) as e:
        RH.plan_target(hm, pin)
    m = str(e.value)
    assert OUT in m and pin.name in m, m
    assert "unreproducible" in m or "cannot be reproduced" in m, m


# ---------------------------------------------------------------- it is a walk, not one hardcoded hop


def test_a_third_pass_layered_over_the_water_pass_still_resolves_the_sculpt(tmp_path):
    """Without this, the next pass over the heightmap breaks --plan exactly as the water pass did.

    The pin here is two passes above the sculpt and no entry on the pinned file names the sculpt directly; the
    only thing that does is `water_shaped_from`, now one layer down the recorded chain.
    """
    pin, out = _chain(tmp_path, pin_body=b"a third pass")
    hm = _hm(pin_name="land_8k_16_rescaled_b145_pads_rift_water_roads.png",
             shadow_shaped_from={"path": PIN_NAME, "sha256": "1" * 64},
             water_shaped_from={"path": OUT, "sha256": _sha(out)})
    current = tmp_path / "land_8k_16_rescaled_b145_pads_rift_water_roads.png"
    current.write_bytes(b"a third pass")
    target, sha, via = RH.plan_target(hm, current)
    assert target == out and sha == _sha(out)
    assert "water_shaped_from" in via, via


def test_plan_target_ignores_provenance_entries_that_are_not_records(tmp_path):
    # Without this, a scalar sibling of the provenance entries (previous_sha256 is a list, revision_note a
    # string, width an int) would raise a TypeError or AttributeError instead of being skipped.
    pin, out = _chain(tmp_path)
    hm = _hm(previous_sha256=["0" * 64], revision_note="a string, not a record", channel="gray",
             water_shaped_from={"path": OUT, "sha256": _sha(out)})
    assert RH.plan_target(hm, pin)[0] == out


# ---------------------------------------------------------------- against the real chain


def test_the_real_heightmap_chain_still_names_and_hashes_the_sculpt_output():
    """Without this, the synthetic fixtures above could all pass while `data/world.json` has stopped recording
    the sculpt's output -- the one condition that makes `derived/rift_sculpt/` unrebuildable.

    Reads the heightmap directory only (hashes one file beside the pin); it does not sculpt and does not run
    `--plan`.
    """
    import terrain as T
    world = T.load_world(ROOT / "data" / "world.json")
    if not (os.environ.get("COBBLERS_SOURCE_ROOT") or world.get("source_root")):
        pytest.skip("COBBLERS_SOURCE_ROOT unset")
    try:
        current = T.resolve_heightmap(world, ROOT / "data" / "world.json")
    except T.TerrainUnavailable as exc:
        pytest.skip(str(exc))
    hm = world["heightmap"]
    target, sha, via = RH.plan_target(hm, current)
    assert target.name == OUT
    assert sha == hashlib.sha256(target.read_bytes()).hexdigest()
    if current.name != OUT:
        assert sha != hm["sha256"], "the pin has moved on, so the sculpt's sha cannot be the pinned one"
        assert via, "a hop was taken and nothing records which entry it went through"
