"""The Lower Galleries entered from the Route 1 old mine, and their retired mouth (2026-10-20, step R9OCR).

The owner, 2026-10-20, between the two entrances: "the left mine is way better and i'd rather have that". The cave
cave_old_mine (data/mining_caves.json) loses its own free-standing frame and stair shaft; its hall is entered from the
old mine's chamber by a passage tools/route1_old_mine.py cuts (lower_way), ending in entry.host.opening; step R9OCR
puts the old mouth back to the heightmap's terrain in a world that has it and cuts the passage there.

Written by the session that built the change (minecraft-systems-dev), NOT by test-author: .claude/rules/testing.md
asks for a different agent, and this file says so instead. What keeps it honest: every expectation is the audit's
(tools/mining_caves_audit.py host_problems, reroute_problems and walk_problems), which reads data/mining_caves.json's
rules text, the frozen record and data/placements.json and imports nothing from tools/mining_caves.py or
tools/route1_old_mine.py; and every proof that it bites MUTATES A GENERATOR's source text (data untouched), as
tests/test_mining_caves_audit.py does. An independent review of this file and of the audit's new checks is still owed.

Every test reads the canonical heightmap and skips, naming it, without one.

Not covered (it needs a running server): that the world's cells match the model (the restore's terrain at the old mouth
is UNVERIFIED offline: grass_block by the paint preset, data/mining_caves.json retired_entry.terrain); that the forceload
and the held count work as the stated vanilla semantics say; what a player built at the old mouth since R9OC.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import mining_caves_audit as A  # noqa: E402
import test_mining_caves_audit as TA  # noqa: E402

OLD_MINE = ROOT / "tools" / "route1_old_mine.py"


@pytest.fixture(scope="module")
def ground():
    try:
        import ground as G
        g = A.cached(G.Ground())
        g(1347, 4080)
    except Exception as exc:  # noqa: BLE001
        pytest.skip("NOT_EXECUTED: the canonical heightmap is not readable here (%s)" % exc)
    return g


def old_mine(mutation=None):
    """tools/route1_old_mine.py as a fresh module, with one (old, new) source edit (it must match exactly once)."""
    src = OLD_MINE.read_text(encoding="utf-8")
    if mutation:
        assert src.count(mutation[0]) == 1, "the mutation %r no longer matches the generator once" % mutation[0][:60]
        src = src.replace(*mutation)
    mod = types.ModuleType("route1_old_mine")
    mod.__file__ = str(OLD_MINE)
    exec(compile(src, str(OLD_MINE), "exec"), mod.__dict__)
    return mod


def real_pack(mutation=None, mine_mutation=None, reroute=True):
    """(spec, functions, the builder's problems) the builder emits for the real data on the real heightmap, the reroute
    functions included; the keep-clear rules are TA._NoClearance's (they need a full checkout: the CLI runs them)."""
    saved = sys.modules.get("route1_old_mine")
    if mine_mutation:
        sys.modules["route1_old_mine"] = old_mine(mine_mutation)
    try:
        mc = TA.builder(mutation)
        mc.Clearance = TA._NoClearance
        spec = A.load()
        plan, probs, _notes = mc.model(spec)
        fns = {"build_%s" % e["cave"]["id"]: mc.build_lines(spec, e) for e in plan}
        fns.update(mc.driver_files(spec, plan))
        g = mc.G.Ground()
        for cave in spec["caves"]:
            if cave.get("retired_entry") and reroute:
                fns.update(mc.reroute_files(spec, cave, g))
        return spec, fns, probs
    finally:
        if mine_mutation:
            if saved is None:
                sys.modules.pop("route1_old_mine", None)
            else:
                sys.modules["route1_old_mine"] = saved


@pytest.fixture(scope="module")
def real(ground):
    return real_pack()


# Without it the change could ship a cave nobody can enter, an old frame left standing, or a restore that buries a
# player: on the real data the builder reports nothing, and the audit's host, reroute and walk checks are clean.
def test_the_real_galleries_are_entered_from_the_old_mine_and_the_old_mouth_is_restored(real, ground):
    spec, fns, probs = real
    assert probs == []
    assert A.host_problems(spec, fns, ground) == []
    assert A.reroute_problems(spec, fns, ground) == []
    assert A.walk_problems(spec, fns, ground) == []


# Without it the owner's change is undone silently by the data: the Lower Galleries keep a mouth of their own, or are
# entered from somewhere other than the old mine. (The Fossick cave, left with its own mouth on 2026-10-20 for want of a
# slope, lost it the same day to a built hill: "make fossick like route 1", tests/test_fossick_adit.py.)
def test_the_old_mine_cave_lost_its_mouth_to_the_old_mine():
    caves = {c["id"]: c for c in A.load()["caves"]}
    assert caves["cave_old_mine"]["entry"]["mouth"] is False
    assert caves["cave_old_mine"]["entry"]["host"]["settlement"] == "route1_old_mine"
    assert caves["cave_old_mine"]["retired_entry"].get("step", "R9OCR") == "R9OCR"


# Without it the opening is written as wall: the passage from the old mine meets a blank face of stone and the
# galleries cannot be reached at all (the builder writes the hole as skin instead of air).
def test_mutation_opening_written_as_wall_is_caught(ground):
    spec, fns, _p = real_pack(('cells[c] = "open"', 'cells[c] = "skin"'))
    assert any("leaves" in p and "opening" in p for p in A.host_problems(spec, fns, ground))
    assert A.walk_problems(spec, fns, ground)


# Without it the cave would keep building its own mouth on a fresh export, and the frame the owner asked to lose
# stands again after the next re-apply.
def test_mutation_mouth_kept_is_caught(ground):
    mut = ('mouth = e.get("mouth", True)', "mouth = True")
    # the builder's own reroute refuses (its CaveError, of the mutated module's own class)
    with pytest.raises(Exception, match="no opening in the hall"):
        real_pack(mut)
    spec, fns, _p = real_pack(mut, reroute=False)       # and the audit catches the build on its own
    assert any("old mouth and incline were" in p for p in A.host_problems(spec, fns, ground))


# Without it a player standing on the old incline's bottom stairs is not held, and the hall's new end wall is written
# over him (the defect the audit found in the first version of the reroute).
def test_mutation_end_wall_not_held_is_caught(ground):
    spec, fns, _p = real_pack(("list(cols.items()) + list(rewrite.items()) + list(_write_cols(connect).items())",
                               "list(cols.items()) + list(_write_cols(connect).items())"))
    assert any("outside every held box" in p for p in A.reroute_problems(spec, fns, ground))


# Without it the restore leaves the old shaft open (only the probes' columns go back): a hole on the flat where the
# frame stood, the thing the owner asked to be rid of.
def test_mutation_restore_skips_the_terrain_is_caught(ground):
    spec, fns, _p = real_pack(("body += LG.terrain_lines(first, ground, t) + own(set(first))", "body += own(set(first))"))
    assert any("core cell(s) of the old mouth wrong" in p for p in A.reroute_problems(spec, fns, ground))


# Without it the passage is cut only where it already exists (the gate inverted) and never in the live world, or is
# cut again on every run over whatever a player put in it.
def test_mutation_passage_gate_inverted_is_caught(ground):
    spec, fns, _p = real_pack(("unless block %d %d %d minecraft:air run function %s",
                               "if block %d %d %d minecraft:air run function %s"))
    assert any("not called once behind" in p for p in A.reroute_problems(spec, fns, ground))


# Without it a timber set at the stairs' foot hangs its lantern at a descending player's head height, and the passage
# cannot be walked (found by the audit's walk on the first version): the walk catches it when the record is rebuilt
# with it, and the reroute catches the passage no longer matching the recorded mine when only the generator moved.
def test_mutation_lantern_at_the_stairs_foot_is_caught(ground, monkeypatch):
    mut = ("sets = [level[0]] + ", "sets = [level[1]] + ")
    spec, fns, _p = real_pack(mine_mutation=mut)
    assert any("differently from what the host's earthwork leaves" in p for p in A.reroute_problems(spec, fns, ground))
    import ground as G
    om = old_mine(mut)
    monkeypatch.setattr(A, "host_lines", lambda cave: om.build(G.Ground()))
    assert A.walk_problems(spec, fns, ground)


# Without it the step is not run, runs before the galleries exist, or its refusal is not read back.
def test_the_reroute_step_is_wired_after_the_caves_and_reads_its_refusal_back(ground):
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert '("R9OCR",' in src and "mining_caves.reroute_steps()" in src
    assert src.index('("R9OC",') < src.index('("R9OCR",') < src.index('("R9CK",')
    import mining_caves as MC
    steps = MC.reroute_steps()
    kinds = [k for k, _v in steps]
    assert kinds == ["cmd", "wait", "fn", "check", "cmd"]
    assert steps[2][1] == "cobblers:mining_caves/reroute/cave_old_mine"
    assert steps[3][1][0] == "chunk_look" and steps[3][1][2] == 0
    assert steps[0][1].startswith("forceload add ") and steps[4][1] == steps[0][1].replace("add", "remove")


# Without it the frozen record could drift from what R9OC actually built, and the restore would undo cells it never
# wrote, or miss ones it did: the frozen build text still hashes to the applied sha256.
def test_the_frozen_build_still_hashes_to_the_applied_one(ground):
    import mining_caves as MC
    cave = next(c for c in MC.load()["caves"] if c["id"] == "cave_old_mine")
    MC.retired_geometry(cave, MC.G.Ground())            # raises CaveError on a mismatch
    assert json.dumps(cave["retired_entry"]["frozen_cave"]["entry"]["anchor"]) == "[1347, 4080]"
