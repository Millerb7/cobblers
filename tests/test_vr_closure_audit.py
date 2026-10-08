"""Victory Road's closure (tools/vr_closure_audit.py): the caves are the only way from the Deep to the League, and
they can be walked to the end.

WRITTEN BY THE IMPLEMENTER (minecraft-systems-dev, 2026-10-08) at the caller's request, against CLAUDE.md principle
16's preference: a separate reviewer should read these against the data before trusting them.

Every mutation here edits the GENERATOR (tools/rift_zones.py), never data/rift_zones.json (CLAUDE.md, "mutate the
generator, not the record"): each one undoes one half of the closure in the code that emits the pack, and the audit,
which reads only the emitted pack, the emitted cave and the heightmap, must name it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rift_zones as RZ  # noqa: E402
import vr_closure_audit as A  # noqa: E402

pytestmark = pytest.mark.slow


def _quiet_report(_a, quiet=False):
    return 0


def zones_pack(module=None):
    """cmd_build into a throwaway directory. The ground is stubbed: it places only walls and gatehouse shells, and
    the audit reads neither (it ignores every wall, which only opens more ground than the world has)."""
    M = module or RZ
    tmp = Path(tempfile.mkdtemp(prefix="vr_closure_"))
    saved = (M.PACKS, M.ground_of, M.cmd_report)
    M.PACKS, M.cmd_report = tmp, _quiet_report
    M.ground_of = lambda _root: (lambda x, z: 80)
    try:
        M.cmd_build(argparse.Namespace(source_root=None))
    finally:
        M.PACKS, M.ground_of, M.cmd_report = saved
    return tmp / M.PACK


def mutant(old, new, label):
    src = (ROOT / "tools" / "rift_zones.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, "the mutation's anchor is gone from tools/rift_zones.py: %r" % old
    mod = types.ModuleType(label)
    mod.__file__ = str(ROOT / "tools" / "rift_zones.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


@pytest.fixture(scope="module")
def caves():
    """The cave's own blocks, built fresh from data/vr_caves.json into a throwaway pack (a stale build/ copy could
    pass or fail for reasons of its own), or a skip naming the missing input."""
    import rift_deep as RD
    import terrain as T
    import vr_caves as V
    pytest.importorskip("PIL", reason="Pillow is needed to trace the Deep's pit from the annotated heightmap")
    root = T.env_source_root()
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    regions = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))
    if not root or not (Path(root) / world["heightmap"]["path"]).is_file():
        pytest.skip("the canonical heightmap is not available: the closure is measured on it")
    ann = Path(root) / regions["source"]["file"].split(" ")[0]
    if not ann.is_file() or hashlib.sha256(ann.read_bytes()).hexdigest() != regions["source"]["sha256"]:
        pytest.skip("the owner's pinned annotated tracing (the Deep's pit) is not available")
    try:
        _plan, _spec, net = V.build(root, None, strict=True)
    except (T.TerrainUnavailable, RD.DeepError) as e:
        pytest.skip("the cave's inputs are unusable: %s" % e)
    out = Path(tempfile.mkdtemp(prefix="vr_closure_caves_")) / "cobblers_vr_caves"
    V.write(V.lines(net), out, "vr_caves", "Victory Road's caves (test)")
    return out


@pytest.fixture(scope="module")
def real(caves):
    return A.audit(zones_pack(), caves)


def test_the_closure_holds_and_the_caves_can_be_walked(real):
    problems, notes, path = real
    assert problems == [], problems
    assert any(n.startswith("caves: a flag holder walks") for n in notes), notes
    assert any(n.startswith("caves without the flag: apron never reached") for n in notes), notes
    # the walk ends on the League's apron, starting at the mouth
    vr = json.loads((ROOT / "data" / "vr_caves.json").read_text(encoding="utf-8"))
    assert abs(path[0][0] - vr["mouth"]["at"][0]) <= 1 and abs(path[0][2] - vr["mouth"]["at"][2]) <= 1
    assert path[-1][1] >= vr["exit"]["lot_y"] + 1


def test_the_surface_walk_still_reaches_g5_and_g5_refuses(real):
    _problems, notes, _path = real
    line = next(n for n in notes if n.startswith("surface:") and "z5_knock" in n)
    assert line.endswith("with: ok"), line


@pytest.mark.parametrize("before", ["vr_caves:build", "rift_zones:build"])
def test_prepare_runs_the_closure_audit_after_both_packs(before):
    import reapply
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root="", server_dir=""))]
    assert names.index(before) < names.index("vr_closure_audit")


def test_g5_granting_on_the_flag_reopens_the_surface(caves):
    # tools/rift_zones.py as it was before 2026-10-08: G5's qualify tests the flag, not the score
    mod = mutant('and p.get("advancements") and p.get("knock_needs_score"):', 'and p.get("advancements") and False:',
                 "rift_zones_g5_on_flag")
    problems, _n, _p = A.audit(zones_pack(mod), caves)
    assert any(p.startswith("SURFACE: z5_knock") for p in problems), problems


def test_admitting_anywhere_in_z5_reopens_the_sky(caves):
    # qualify on entry everywhere, as 33c277c shipped it: a flier holding the flag is admitted over the precinct
    mod = mutant('where = [""] if vols is None else [",%s" % sel_box(v) for v in vols]', 'where = [""]',
                 "rift_zones_admit_anywhere")
    problems, _n, _p = A.audit(zones_pack(mod), caves, with_surface=False)
    assert any(p.startswith("SKY:") and "admit or grant" in p for p in problems), problems


def test_dropping_the_precinct_leaves_the_league_open_to_fliers(caves):
    mod = mutant('for b in zone_boxes(z)]', 'for b in z["boxes"]]', "rift_zones_no_precinct")
    problems, _n, _p = A.audit(zones_pack(mod), caves, with_surface=False)
    assert any(p.startswith("no zone check holds the League's lot") for p in problems), problems
    assert any(p.startswith("SKY:") and "League's lot" in p for p in problems), problems


def test_an_admit_ground_that_misses_crossings_turns_cave_walkers_back(caves):
    # the admit volumes cut back to the boxes wholly south of z2680: the caves' crossings at z2655-2679 are then
    # outside them, and a flag holder walking up is turned back there
    mod = mutant('for b in z["boxes"] if b[3] >= aw["from_z"]]', 'for b in z["boxes"] if b[1] >= aw["from_z"] + 60]',
                 "rift_zones_admit_misses")
    problems, _n, _p = A.audit(zones_pack(mod), caves, with_surface=False)
    assert any(p.startswith("CAVES: a flag holder walking up from the mouth is turned back") for p in problems), problems
